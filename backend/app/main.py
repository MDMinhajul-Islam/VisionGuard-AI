from __future__ import annotations

import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import cv2
import mediapipe
import torch
import torchvision
from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import __version__
from app.core.config import get_settings
from app.core.audit import record_audit
from app.core.authorization import (
    accessible_video_ids, authorize_object_request, authorize_video, membership_for, resolve_scope,
)
from app.core.rate_limit import login_limiter
from app.core.security import (
    DUMMY_PASSWORD_HASH, SESSION_COOKIE, authenticate_session, create_access_token, hash_password, normalize_email,
    require_roles, revoke_all_user_sessions, revoke_session, verify_password,
)
from app.database import get_db, init_db
from app.database.session import SessionLocal, request_database_context
from app.database.models import (
    AuditEvent, CandidateEvent, DatasetAsset, EmbeddingCache, ExportedClip, ObjectDetection, Organization,
    OrganizationMembership, PoseEvidence, ProcessingJob, SafetyZone, Site, SiteAccess, User,
    ValidationAnnotation, Video, VideoFrame, now_iso,
)
from app.schemas.api import (
    AnnotationCreate, AnnotationOut, DatasetAssetCreate, DatasetAssetOut, EvaluationRequest, ExportRequest, JobOut,
    ProcessRequest, ReviewUpdate, SearchRequest, SearchResponse, SearchResult,
    LoginRequest, MembershipCreate, MembershipOut, OrganizationCreate, OrganizationOut,
    PasswordChange, SiteCreate, SiteOut, UserCreate, UserOut, VideoOut, ZoneAnalysisRequest, ZoneCreate,
)
from app.evaluation.annotations import deterministic_annotation_id
from app.evaluation.metrics import IntervalEvent, evaluate_events, temporal_iou
from app.evaluation.video_level import VideoPrediction, evaluate_video_predictions
from app.services.exporter import export_clip
from app.services.video_io import SUPPORTED_EXTENSIONS, find_binary, probe_video, render_overlay, safe_within
from app.vision.clip_engine import clip_engine
from app.vision.pose_diagnostics import (
    BASELINE_PROFILE, IMPROVED_PROFILE, diagnostic_series, observation_from_landmarks,
    run_profile, summarize_diagnostics,
)
from app.vision.motion_fusion import MOTION_FUSION_PROFILE, detect_motion_fusion_events
from app.vision.object_detector import object_detector
from app.vision.obstruction_detection import ObstructionSample, detect_persistent_obstructions
from app.vision.pose_engine import pose_engine
from app.vision.video_processor import process_video_job
from app.workers.job_queue import job_queue
from app.workers.recovery import recover_processing_jobs


settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("visionguard.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    recovery = recover_processing_jobs()
    logger.info("job recovery: %s", recovery)
    yield


app = FastAPI(
    title="VisionGuard AI API",
    version=__version__,
    description="Local-only research API for authorized recorded-video analysis. Human review is required.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Organization-ID", "X-Site-ID", "X-Request-ID"],
)


PUBLIC_PATHS = {"/api/health", "/api/auth/login", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def authentication_gate(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or str(uuid4())
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS or not request.url.path.startswith("/api/"):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response
    authorization = request.headers.get("authorization", "")
    token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else request.cookies.get(SESSION_COOKIE)
    if not token:
        return JSONResponse(status_code=401, content={"detail": {"code": "authentication_required", "message": "Authentication is required."}}, headers={"X-Request-ID": request.state.request_id})
    try:
        request.state.user, payload = authenticate_session(token)
        request.state.session_jti = payload["jti"]
    except HTTPException as error:
        return JSONResponse(status_code=error.status_code, content={"detail": {"code": "invalid_session", "message": str(error.detail)}}, headers={"X-Request-ID": request.state.request_id})
    if not authorization and request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        origin = request.headers.get("origin")
        if origin not in settings.frontend_origins:
            return JSONResponse(status_code=403, content={"detail": {"code": "csrf_origin_rejected", "message": "Request origin is not allowed."}}, headers={"X-Request-ID": request.state.request_id})
    try:
        authorize_object_request(request, request.state.user)
    except HTTPException as error:
        with SessionLocal() as audit_db:
            record_audit(audit_db, request, "authorization.object_access", "denied", actor=request.state.user, organization_id=getattr(request.state, "organization_id", None), object_type="api_path", metadata={"method": request.method, "path": request.url.path})
            audit_db.commit()
        return JSONResponse(status_code=error.status_code, content={"detail": {"code": "resource_not_found", "message": "Resource not found."}}, headers={"X-Request-ID": request.state.request_id})
    with request_database_context(
        request.state.user.id,
        getattr(request.state, "organization_id", None),
        (request.state.site_id,) if getattr(request.state, "site_id", None) else (),
    ):
        response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    logger.info("%s %s -> %s %.1fms", request.method, request.url.path, response.status_code, (time.perf_counter() - started) * 1000)
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, error: ValueError):
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": str(error)}})


def video_out(video: Video) -> VideoOut:
    return VideoOut.model_validate(video).model_copy(update={
        "thumbnail_url": f"/api/videos/{video.id}/thumbnail" if video.thumbnail_path else None,
        "media_url": f"/api/videos/{video.id}/media",
    })


def event_dict(event: CandidateEvent):
    return {
        "id": event.id, "video_id": event.video_id, "event_type": event.event_type,
        "label": event.label, "start_seconds": event.start_seconds, "end_seconds": event.end_seconds,
        "processing_method": event.processing_method, "model_version": event.model_version,
        "raw_scores": json.loads(event.raw_scores_json), "thresholds": json.loads(event.thresholds_json),
        "supporting_frames": json.loads(event.supporting_frames_json),
        "review_status": event.review_status, "reviewer_note": event.reviewer_note,
        "synthetic_fixture": event.synthetic_fixture, "created_at": event.created_at,
    }


def dataset_asset_dict(asset: DatasetAsset, db: Session) -> dict:
    video = db.get(Video, asset.video_id)
    latest_job = db.scalar(select(ProcessingJob).where(ProcessingJob.video_id == asset.video_id).order_by(ProcessingJob.created_at.desc()))
    events = db.scalars(select(CandidateEvent).where(
        CandidateEvent.video_id == asset.video_id,
        CandidateEvent.event_type == "potential_fall",
        CandidateEvent.synthetic_fixture.is_(False),
    ).order_by(CandidateEvent.start_seconds)).all()
    return {
        "id": asset.id, "video_id": asset.video_id, "dataset_name": asset.dataset_name,
        "original_recording_id": asset.original_recording_id,
        "evaluation_label": asset.evaluation_label, "detailed_label": asset.detailed_label,
        "source_url": asset.source_url, "source_license": asset.source_license,
        "annotation_status": asset.annotation_status,
        "manifest_record": json.loads(asset.manifest_record_json), "imported_at": asset.imported_at,
        "video": video_out(video).model_dump() if video else None,
        "latest_job": JobOut.model_validate(latest_job).model_dump() if latest_job else None,
        "predicted_fall": bool(events), "predicted_event_count": len(events),
        "predicted_events": [event_dict(event) for event in events],
    }


@app.get("/api/health")
def health():
    tools = {}
    for name in ("ffmpeg", "ffprobe"):
        try:
            tools[name] = str(find_binary(name))
        except FileNotFoundError:
            tools[name] = None
    return {"status": "ok", "mode": "local-research", "version": __version__, "tools": tools}


@app.post("/api/auth/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_key = f"{request.client.host if request.client else 'unknown'}:{body.email.strip().casefold()}"
    if not login_limiter.allow(rate_key, settings.login_rate_limit_attempts, settings.login_rate_limit_window_seconds):
        record_audit(db, request, "authentication.login", "rate_limited")
        db.commit()
        raise HTTPException(429, "invalid credentials")
    user = db.scalar(select(User).where(User.email == normalize_email(body.email)))
    password_valid = verify_password(body.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or user.disabled or not password_valid:
        # The response intentionally does not distinguish missing, disabled, or wrong-password accounts.
        record_audit(db, request, "authentication.login", "denied", actor=user if user and not user.disabled else None)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    token = create_access_token(user, db)
    login_limiter.clear(rate_key)
    record_audit(db, request, "authentication.login", "success", actor=user)
    db.commit()
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=settings.auth_cookie_secure,
        samesite="strict", max_age=settings.auth_token_minutes * 60, path="/",
    )
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    revoke_session(request.state.session_jti)
    record_audit(db, request, "authentication.logout", "success", actor=user)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/", samesite="strict")


@app.get("/api/auth/me", response_model=UserOut)
def auth_me(user: User = Depends(require_roles("admin", "reviewer"))):
    return user


@app.post("/api/auth/change-password", status_code=204)
def change_password(body: PasswordChange, request: Request, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    stored = db.get(User, user.id)
    if not stored or not verify_password(body.current_password, stored.password_hash):
        raise HTTPException(400, "password change failed")
    stored.password_hash = hash_password(body.new_password)
    revoke_all_user_sessions(stored, db)
    record_audit(db, request, "authentication.password_changed", "success", actor=stored)
    db.commit()


@app.post("/api/admin/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))):
    email = normalize_email(body.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "email is already registered")
    user = User(
        email=email, display_name=body.display_name.strip(),
        password_hash=hash_password(body.password), role=body.role,
    )
    db.add(user)
    db.flush()
    record_audit(db, request, "administration.user_created", "success", actor=actor, object_type="user", object_id=user.id)
    db.commit()
    db.refresh(user)
    return user


@app.post("/api/admin/organizations", response_model=OrganizationOut, status_code=201)
def create_organization(body: OrganizationCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))):
    if db.scalar(select(Organization).where(func.lower(Organization.name) == body.name.strip().lower())):
        raise HTTPException(409, "organization already exists")
    organization = Organization(name=body.name.strip(), workspace_type=body.workspace_type)
    db.add(organization); db.flush()
    record_audit(db, request, "administration.organization_created", "success", actor=actor, organization_id=organization.id, object_type="organization", object_id=organization.id)
    db.commit(); db.refresh(organization)
    return organization


@app.get("/api/organizations")
def list_organizations(db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    memberships = db.scalars(select(OrganizationMembership).where(
        OrganizationMembership.user_id == user.id, OrganizationMembership.status == "active"
    )).all()
    result = []
    for membership in memberships:
        organization = db.get(Organization, membership.organization_id)
        sites = db.scalars(select(Site).where(Site.organization_id == membership.organization_id)).all()
        allowed_sites = sites if membership.role == "organization_admin" else [site for site in sites if db.scalar(select(SiteAccess.id).where(SiteAccess.membership_id == membership.id, SiteAccess.site_id == site.id))]
        if organization:
            result.append({
                **OrganizationOut.model_validate(organization).model_dump(),
                "membership_role": membership.role,
                "sites": [SiteOut.model_validate(site).model_dump() for site in allowed_sites],
            })
    return result


@app.post("/api/admin/organizations/{organization_id}/sites", response_model=SiteOut, status_code=201)
def create_site(organization_id: str, body: SiteCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))):
    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(404, "organization not found")
    site = Site(organization_id=organization_id, name=body.name.strip())
    db.add(site); db.flush()
    record_audit(db, request, "administration.site_created", "success", actor=actor, organization_id=organization_id, object_type="site", object_id=site.id)
    db.commit(); db.refresh(site)
    return site


@app.post("/api/admin/organizations/{organization_id}/memberships", response_model=MembershipOut, status_code=201)
def create_membership(organization_id: str, body: MembershipCreate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin"))):
    if not db.get(Organization, organization_id) or not db.get(User, body.user_id):
        raise HTTPException(404, "organization or user not found")
    existing = membership_for(db, body.user_id, organization_id)
    membership = existing or OrganizationMembership(user_id=body.user_id, organization_id=organization_id, role=body.role)
    membership.role = body.role; membership.status = "active"
    db.add(membership); db.flush()
    db.query(SiteAccess).filter(SiteAccess.membership_id == membership.id).delete()
    valid_sites = set(db.scalars(select(Site.id).where(Site.organization_id == organization_id, Site.id.in_(body.site_ids))).all())
    if valid_sites != set(body.site_ids):
        raise HTTPException(422, "site access contains a site outside the organization")
    for site_id in valid_sites:
        db.add(SiteAccess(membership_id=membership.id, site_id=site_id))
    record_audit(db, request, "administration.membership_changed", "success", actor=actor, organization_id=organization_id, object_type="membership", object_id=membership.id, metadata={"role": body.role, "site_count": len(valid_sites)})
    db.commit(); db.refresh(membership)
    return membership


@app.get("/api/admin/audit")
def list_audit_events(organization_id: str, limit: int = 100, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    membership = membership_for(db, user.id, organization_id)
    if not membership or membership.role != "organization_admin":
        raise HTTPException(404, "resource not found")
    rows = db.scalars(select(AuditEvent).where(AuditEvent.organization_id == organization_id).order_by(AuditEvent.created_at.desc()).limit(min(max(limit, 1), 500))).all()
    return [{
        "id": row.id, "actor_id": row.actor_id, "organization_id": row.organization_id,
        "action": row.action, "object_type": row.object_type, "object_id": row.object_id,
        "outcome": row.outcome, "request_id": row.request_id,
        "metadata": json.loads(row.metadata_json), "created_at": row.created_at,
    } for row in rows]


@app.get("/api/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    visible = accessible_video_ids(db, user)
    count = lambda model, video_column, *criteria: db.scalar(select(func.count()).select_from(model).where(video_column.in_(visible), *criteria)) or 0
    return {
        "videos": count(Video, Video.id), "jobs": count(ProcessingJob, ProcessingJob.video_id),
        "indexed_videos": count(Video, Video.id, Video.status == "indexed"),
        "candidate_events": count(CandidateEvent, CandidateEvent.video_id),
        "pending_review": count(CandidateEvent, CandidateEvent.video_id, CandidateEvent.review_status == "pending"),
        "processing_failures": count(ProcessingJob, ProcessingJob.video_id, ProcessingJob.status == "failed"),
    }


@app.post("/api/videos/upload", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
async def upload_video(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "reviewer"))):
    organization, site, _ = resolve_scope(db, actor, request.headers.get("x-organization-id"), request.headers.get("x-site-id"), "manage")
    original = Path(file.filename or "upload.mp4").name
    extension = Path(original).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(415, detail={"code": "unsupported_format", "message": "Supported formats: MP4, M4V, MOV"})
    identifier = str(uuid4())
    stored_name = f"{identifier}{extension}"
    destination = safe_within(settings.uploads_dir / organization.workspace_type / organization.id / site.id / stored_name, settings.uploads_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    total = 0
    try:
        with destination.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(413, detail={"code": "upload_too_large", "message": f"Upload limit is {settings.max_upload_mb} MB"})
                handle.write(chunk)
        metadata = probe_video(destination)
        if metadata["duration_seconds"] <= 0 or metadata["width"] <= 0:
            raise ValueError("video metadata is invalid")
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    video = Video(
        id=identifier, organization_id=organization.id, site_id=site.id,
        original_filename=original, stored_filename=stored_name,
        path=str(destination), mime_type="video/mp4", size_bytes=total,
        duration_seconds=metadata["duration_seconds"], width=metadata["width"], height=metadata["height"],
        fps=metadata["fps"], codec=metadata["codec"], status="uploaded",
    )
    db.add(video)
    record_audit(db, request, "video.uploaded", "success", actor=actor, organization_id=organization.id, object_type="video", object_id=video.id, metadata={"site_id": site.id, "size_bytes": total})
    db.commit()
    return video_out(video)


@app.get("/api/videos", response_model=list[VideoOut])
def list_videos(db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    visible = accessible_video_ids(db, user)
    return [video_out(item) for item in db.scalars(select(Video).where(Video.id.in_(visible)).order_by(Video.created_at.desc())).all()]


@app.get("/api/videos/{video_id}", response_model=VideoOut)
def get_video(video_id: str, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "video not found")
    return video_out(video)


@app.get("/api/videos/{video_id}/media")
def video_media(video_id: str, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "reviewer"))):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "video not found")
    path = safe_within(Path(video.path), settings.uploads_dir)
    record_audit(db, request, "video.media_accessed", "success", actor=actor, organization_id=video.organization_id, object_type="video", object_id=video.id)
    db.commit()
    return FileResponse(path, media_type=video.mime_type, filename=video.original_filename)


@app.get("/api/videos/{video_id}/thumbnail")
def video_thumbnail(video_id: str, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video or not video.thumbnail_path:
        raise HTTPException(404, "thumbnail not available")
    return FileResponse(safe_within(Path(video.thumbnail_path), settings.frames_dir), media_type="image/jpeg")


@app.post("/api/videos/{video_id}/process", response_model=JobOut, status_code=202)
def process_video(video_id: str, body: ProcessRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "reviewer"))):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "video not found")
    active = db.scalar(select(ProcessingJob).where(ProcessingJob.video_id == video_id, ProcessingJob.status.in_(["queued", "running"])))
    if active:
        raise HTTPException(409, "video already has an active processing job")
    reviewed = db.scalar(select(func.count()).select_from(CandidateEvent).where(
        CandidateEvent.video_id == video_id,
        CandidateEvent.synthetic_fixture.is_(False),
        CandidateEvent.review_status != "pending",
    )) or 0
    if reviewed and not body.allow_reprocess_reviewed:
        raise HTTPException(409, detail={
            "code": "reviewed_events_exist",
            "message": "Reprocessing would invalidate reviewed model evidence. Export/preserve it first or explicitly set allow_reprocess_reviewed=true.",
        })
    organization = db.get(Organization, video.organization_id)
    if body.enable_clip and (not organization or organization.workspace_type != "research"):
        raise HTTPException(403, "CLIP is restricted to explicitly designated research workspaces")
    job = ProcessingJob(video_id=video_id, config_json=body.model_dump_json())
    db.add(job)
    db.flush()
    record_audit(db, request, "processing.job_created", "success", actor=actor, organization_id=video.organization_id, object_type="processing_job", object_id=job.id, metadata={"video_id": video.id})
    db.commit()
    job_queue.submit(job.id, process_video_job)
    return job


@app.get("/api/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


@app.post("/api/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "reviewer"))):
    job = db.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if job.status not in {"queued", "running"}:
        raise HTTPException(409, "job is not cancellable")
    job.cancel_requested = True
    video = db.get(Video, job.video_id)
    record_audit(db, request, "processing.job_cancel_requested", "success", actor=actor, organization_id=video.organization_id if video else None, object_type="processing_job", object_id=job.id)
    db.commit()
    return job


@app.post("/api/videos/{video_id}/search", response_model=SearchResponse)
def semantic_search(video_id: str, request: SearchRequest, db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    organization = db.get(Organization, video.organization_id) if video else None
    if not organization or organization.workspace_type != "research":
        raise HTTPException(403, "CLIP semantic search is restricted to research workspaces")
    cache = db.scalar(select(EmbeddingCache).where(EmbeddingCache.video_id == video_id))
    if not cache:
        raise HTTPException(409, "video has no CLIP index")
    started = time.perf_counter()
    matches = clip_engine.search(Path(cache.path), request.query, request.top_k, request.temporal_suppression_seconds)
    return SearchResponse(
        query=request.query, model=cache.model_name,
        score_warning="Cosine similarity is a relative retrieval signal, not a calibrated probability.",
        elapsed_ms=(time.perf_counter() - started) * 1000,
        results=[SearchResult(**item, preview_url=f"/api/frames/{item['frame_id']}/image") for item in matches],
    )


@app.get("/api/videos/{video_id}/frames")
def list_frames(video_id: str, limit: int = 200, db: Session = Depends(get_db)):
    frames = db.scalars(select(VideoFrame).where(VideoFrame.video_id == video_id).order_by(VideoFrame.timestamp_seconds).limit(min(max(limit, 1), 1000))).all()
    return [{"id": item.id, "timestamp_seconds": item.timestamp_seconds, "frame_number": item.frame_number, "clip_indexed": item.clip_indexed, "image_url": f"/api/frames/{item.id}/image", "overlay_url": f"/api/frames/{item.id}/overlay"} for item in frames]


@app.get("/api/frames/{frame_id}/image")
def frame_image(frame_id: str, db: Session = Depends(get_db)):
    frame = db.get(VideoFrame, frame_id)
    if not frame:
        raise HTTPException(404, "frame not found")
    return FileResponse(safe_within(Path(frame.path), settings.frames_dir), media_type="image/jpeg")


@app.get("/api/frames/{frame_id}/overlay")
def frame_overlay(frame_id: str, db: Session = Depends(get_db)):
    frame = db.get(VideoFrame, frame_id)
    if not frame:
        raise HTTPException(404, "frame not found")
    image = cv2.imread(str(safe_within(Path(frame.path), settings.frames_dir)))
    rows = db.scalars(select(ObjectDetection).where(ObjectDetection.frame_id == frame_id)).all()
    detections = []
    for row in rows:
        x1, y1, x2, y2 = json.loads(row.bbox_json)
        detections.append({"label": row.label, "confidence": row.confidence, "track_id": row.track_id, "bbox_pixels": (x1 * frame.width, y1 * frame.height, x2 * frame.width, y2 * frame.height)})
    zones = db.scalars(select(SafetyZone).where(SafetyZone.video_id == frame.video_id)).all()
    poses = db.scalars(select(PoseEvidence).where(PoseEvidence.frame_id == frame_id)).all()
    pose = min(poses, key=lambda item: abs(item.timestamp_seconds - frame.timestamp_seconds)) if poses else None
    rendered = render_overlay(
        image, detections, [json.loads(zone.polygon_json) for zone in zones],
        json.loads(pose.landmarks_json) if pose else None,
    )
    ok, encoded = cv2.imencode(".jpg", rendered)
    if not ok:
        raise HTTPException(500, "overlay encoding failed")
    return __import__("fastapi").responses.Response(content=encoded.tobytes(), media_type="image/jpeg")


@app.get("/api/frames/{frame_id}/evidence")
def frame_evidence(frame_id: str, db: Session = Depends(get_db)):
    frame = db.get(VideoFrame, frame_id)
    if not frame:
        raise HTTPException(404, "frame not found")
    detections = db.scalars(select(ObjectDetection).where(ObjectDetection.frame_id == frame_id)).all()
    poses = db.scalars(select(PoseEvidence).where(PoseEvidence.frame_id == frame_id).order_by(PoseEvidence.sync_error_seconds)).all()
    zones = db.scalars(select(SafetyZone).where(SafetyZone.video_id == frame.video_id)).all()
    return {
        "frame_id": frame.id, "timestamp_seconds": frame.timestamp_seconds,
        "image_url": f"/api/frames/{frame.id}/image", "overlay_url": f"/api/frames/{frame.id}/overlay",
        "detections": [{
            "id": item.id, "label": item.label, "confidence": item.confidence,
            "bbox": json.loads(item.bbox_json), "track_id": item.track_id,
        } for item in detections],
        "pose_samples": [{
            "timestamp_seconds": item.timestamp_seconds,
            "frame_timestamp_seconds": item.frame_timestamp_seconds,
            "sync_error_seconds": item.sync_error_seconds,
            "landmarks": json.loads(item.landmarks_json), "signals": json.loads(item.signals_json),
            "sufficient_evidence": item.sufficient_evidence,
        } for item in poses],
        "zones": [{"id": item.id, "name": item.name, "polygon": json.loads(item.polygon_json)} for item in zones],
    }


@app.get("/api/videos/{video_id}/detections")
def detections(video_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(select(ObjectDetection).where(ObjectDetection.video_id == video_id).order_by(ObjectDetection.timestamp_seconds)).all()
    return [{"id": row.id, "frame_id": row.frame_id, "timestamp_seconds": row.timestamp_seconds, "label": row.label, "confidence": row.confidence, "bbox": json.loads(row.bbox_json), "track_id": row.track_id} for row in rows]


@app.get("/api/videos/{video_id}/analysis-timeline")
def analysis_timeline(
    video_id: str, start_seconds: float = 0, end_seconds: float | None = None,
    limit: int = 2000, db: Session = Depends(get_db),
    actor: User = Depends(require_roles("admin", "reviewer")),
):
    """Bounded genuine inference samples for tenant-authorized synchronized playback."""
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(404, "video not found")
    authorize_video(db, actor, video, "read")
    start = max(0.0, start_seconds)
    end = min(video.duration_seconds or start + 300, end_seconds if end_seconds is not None else start + 300)
    if end < start or end - start > 300:
        raise HTTPException(422, "timeline window must be between 0 and 300 seconds")
    bounded_limit = min(max(limit, 1), 5000)
    frames = db.scalars(select(VideoFrame).where(
        VideoFrame.video_id == video_id, VideoFrame.timestamp_seconds >= start,
        VideoFrame.timestamp_seconds <= end,
    ).order_by(VideoFrame.timestamp_seconds).limit(bounded_limit)).all()
    frame_ids = [item.id for item in frames]
    detection_rows = db.scalars(select(ObjectDetection).where(ObjectDetection.frame_id.in_(frame_ids)).order_by(ObjectDetection.timestamp_seconds)).all() if frame_ids else []
    pose_rows = db.scalars(select(PoseEvidence).where(PoseEvidence.frame_id.in_(frame_ids)).order_by(PoseEvidence.timestamp_seconds)).all() if frame_ids else []
    by_frame: dict[str, list] = {}
    for item in detection_rows:
        by_frame.setdefault(item.frame_id, []).append(item)
    poses_by_frame: dict[str, list] = {}
    for item in pose_rows:
        poses_by_frame.setdefault(item.frame_id, []).append(item)
    zone_rows = db.scalars(select(SafetyZone).where(SafetyZone.video_id == video_id)).all()
    event_rows = db.scalars(select(CandidateEvent).where(
        CandidateEvent.video_id == video_id, CandidateEvent.end_seconds >= start,
        CandidateEvent.start_seconds <= end,
    ).order_by(CandidateEvent.start_seconds)).all()
    latest_job = db.scalar(select(ProcessingJob).where(
        ProcessingJob.video_id == video_id, ProcessingJob.status == "completed",
    ).order_by(ProcessingJob.completed_at.desc()))
    config = json.loads(latest_job.config_json) if latest_job else {}
    return {
        "video": {"id": video.id, "duration_seconds": video.duration_seconds, "width": video.width, "height": video.height, "fps": video.fps, "media_url": f"/api/videos/{video.id}/media"},
        "window": {"start_seconds": start, "end_seconds": end, "sample_count": len(frames), "truncated": len(frames) == bounded_limit},
        "provenance": {
            "processing_job_id": latest_job.id if latest_job else None,
            "detector_model": object_detector.model_name,
            "detector_architecture": object_detector.metadata.architecture,
            "detector_version": object_detector.metadata.model_version,
            "pose_model": pose_engine.model_name,
            "analysis_fps": config.get("analysis_fps"), "pose_fps": config.get("pose_fps"),
            "note": "Only stored sampled inference is returned; no boxes or landmarks are interpolated.",
        },
        "samples": [{
            "frame_id": frame.id, "timestamp_seconds": frame.timestamp_seconds,
            "image_url": f"/api/frames/{frame.id}/image",
            "detections": [{"id": item.id, "label": item.label, "confidence": item.confidence, "bbox": json.loads(item.bbox_json), "track_id": item.track_id} for item in by_frame.get(frame.id, [])],
            "poses": [{"timestamp_seconds": item.timestamp_seconds, "landmarks": json.loads(item.landmarks_json), "signals": json.loads(item.signals_json), "sufficient_evidence": item.sufficient_evidence, "sync_error_seconds": item.sync_error_seconds} for item in poses_by_frame.get(frame.id, [])],
        } for frame in frames],
        "zones": [{"id": item.id, "name": item.name, "zone_type": item.zone_type, "polygon": json.loads(item.polygon_json)} for item in zone_rows],
        "events": [event_dict(item) for item in event_rows],
    }


@app.post("/api/videos/{video_id}/zones", status_code=201)
def create_zone(video_id: str, request: ZoneCreate, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "reviewer"))):
    if not db.get(Video, video_id):
        raise HTTPException(404, "video not found")
    zone = SafetyZone(video_id=video_id, name=request.name, zone_type=request.zone_type, polygon_json=json.dumps(request.polygon))
    db.add(zone)
    db.commit()
    return {"id": zone.id, "video_id": zone.video_id, "name": zone.name, "zone_type": zone.zone_type, "polygon": request.polygon}


@app.get("/api/videos/{video_id}/zones")
def zones(video_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(select(SafetyZone).where(SafetyZone.video_id == video_id)).all()
    return [{"id": row.id, "name": row.name, "zone_type": row.zone_type, "polygon": json.loads(row.polygon_json)} for row in rows]


@app.post("/api/videos/{video_id}/zones/analyze")
def analyze_zones(video_id: str, request: ZoneAnalysisRequest = ZoneAnalysisRequest(), db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "reviewer"))):
    zone_rows = db.scalars(select(SafetyZone).where(SafetyZone.video_id == video_id)).all()
    detection_rows = db.scalars(select(ObjectDetection).where(ObjectDetection.video_id == video_id)).all()
    reviewed_events = db.scalars(select(CandidateEvent).where(
        CandidateEvent.video_id == video_id,
        CandidateEvent.event_type.in_(["potential_exit_obstruction", "potential_walkway_obstruction"]),
        CandidateEvent.review_status != "pending",
    )).all()
    db.execute(delete(CandidateEvent).where(
        CandidateEvent.video_id == video_id,
        CandidateEvent.event_type.in_(["potential_exit_obstruction", "potential_walkway_obstruction"]),
        CandidateEvent.review_status == "pending",
    ))
    created = []
    for zone in zone_rows:
        polygon = json.loads(zone.polygon_json)
        samples = [ObstructionSample(row.timestamp_seconds, row.label, tuple(json.loads(row.bbox_json)), row.confidence, row.frame_id, row.track_id) for row in detection_rows]
        for event in detect_persistent_obstructions(
            samples, polygon, request.min_zone_occupancy, request.min_duration,
            request.max_gap, request.event_merge_interval,
        ):
            event_type = "potential_exit_obstruction" if zone.zone_type == "emergency_exit" else "potential_walkway_obstruction"
            proposed = IntervalEvent("proposed", event.start_seconds, event.end_seconds, event_type)
            if any(
                json.loads(item.raw_scores_json).get("zone_id") == zone.id
                and temporal_iou(proposed, IntervalEvent(item.id, item.start_seconds, item.end_seconds, item.event_type)) >= 0.5
                for item in reviewed_events
            ):
                continue
            candidate = CandidateEvent(
                video_id=video_id, event_type=event_type,
                label="Potential Exit Obstruction — Review Required" if zone.zone_type == "emergency_exit" else "Potential Walkway Obstruction — Review Required",
                start_seconds=event.start_seconds, end_seconds=event.end_seconds,
                processing_method="manual_zone_bbox_persistence", model_version=object_detector.model_name,
                raw_scores_json=json.dumps({
                    "zone_id": zone.id, "zone_name": zone.name, "zone_polygon": polygon,
                    "max_zone_occupancy": event.max_zone_occupancy, "labels": event.labels,
                    "contributing_detections": event.evidence,
                }),
                thresholds_json=json.dumps({
                    "min_zone_occupancy": request.min_zone_occupancy,
                    "min_duration": request.min_duration, "max_gap": request.max_gap,
                    "event_merge_interval": request.event_merge_interval,
                    "profile_name": request.profile_name,
                }),
                supporting_frames_json=json.dumps(event.supporting_frames),
            )
            db.add(candidate)
            db.flush()
            created.append(event_dict(candidate))
    db.commit()
    return {"events_created": len(created), "events": created}


@app.get("/api/videos/{video_id}/events")
def video_events(video_id: str, event_type: str | None = None, db: Session = Depends(get_db)):
    query = select(CandidateEvent).where(CandidateEvent.video_id == video_id)
    if event_type:
        query = query.where(CandidateEvent.event_type == event_type)
    return [event_dict(item) for item in db.scalars(query.order_by(CandidateEvent.start_seconds)).all()]


@app.get("/api/events")
def all_events(status_filter: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    query = select(CandidateEvent).where(CandidateEvent.video_id.in_(accessible_video_ids(db, user)))
    if status_filter:
        query = query.where(CandidateEvent.review_status == status_filter)
    return [event_dict(item) for item in db.scalars(query.order_by(CandidateEvent.created_at.desc())).all()]


@app.get("/api/events/{event_id}")
def get_event(event_id: str, db: Session = Depends(get_db)):
    event = db.get(CandidateEvent, event_id)
    if not event:
        raise HTTPException(404, "event not found")
    return event_dict(event)


@app.get("/api/events/{event_id}/evidence")
def get_event_evidence(event_id: str, db: Session = Depends(get_db)):
    event = db.get(CandidateEvent, event_id)
    if not event:
        raise HTTPException(404, "event not found")
    supporting_ids = set(json.loads(event.supporting_frames_json))
    frames = db.scalars(select(VideoFrame).where(
        VideoFrame.video_id == event.video_id,
        VideoFrame.timestamp_seconds >= max(0, event.start_seconds - 0.5),
        VideoFrame.timestamp_seconds <= event.end_seconds + 0.5,
    ).order_by(VideoFrame.timestamp_seconds)).all()
    for item in db.scalars(select(VideoFrame).where(VideoFrame.id.in_(supporting_ids))).all() if supporting_ids else []:
        if item not in frames:
            frames.append(item)
    frames.sort(key=lambda item: item.timestamp_seconds)
    return {
        "event": event_dict(event),
        "frames": [{
            "id": item.id, "timestamp_seconds": item.timestamp_seconds,
            "is_supporting": item.id in supporting_ids,
            "image_url": f"/api/frames/{item.id}/image",
            "overlay_url": f"/api/frames/{item.id}/overlay",
            "evidence_url": f"/api/frames/{item.id}/evidence",
        } for item in frames],
    }


@app.post("/api/validation/annotations", response_model=AnnotationOut, status_code=201)
def create_annotation(request: AnnotationCreate, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "reviewer"))):
    video = db.get(Video, request.video_id)
    if not video:
        raise HTTPException(404, "video not found")
    authorize_video(db, actor, video, "manage")
    if video.duration_seconds is not None and request.end_seconds > video.duration_seconds + 1e-6:
        raise HTTPException(422, "annotation exceeds video duration")
    identifier = deterministic_annotation_id(request)
    existing = db.get(ValidationAnnotation, identifier)
    if existing:
        return existing
    annotation = ValidationAnnotation(id=identifier, **request.model_dump())
    db.add(annotation)
    db.commit()
    return annotation


@app.get("/api/validation/annotations", response_model=list[AnnotationOut])
def list_annotations(video_id: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    query = select(ValidationAnnotation).where(ValidationAnnotation.video_id.in_(accessible_video_ids(db, user)))
    if video_id:
        query = query.where(ValidationAnnotation.video_id == video_id)
    return db.scalars(query.order_by(ValidationAnnotation.video_id, ValidationAnnotation.start_seconds)).all()


@app.delete("/api/validation/annotations/{annotation_id}", status_code=204)
def delete_annotation(annotation_id: str, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "reviewer"))):
    annotation = db.get(ValidationAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(404, "annotation not found")
    db.delete(annotation)
    db.commit()


@app.post("/api/videos/{video_id}/evaluate")
def evaluate_video(video_id: str, request: EvaluationRequest, db: Session = Depends(get_db), _: User = Depends(require_roles("admin", "reviewer"))):
    positives = db.scalars(select(ValidationAnnotation).where(
        ValidationAnnotation.video_id == video_id,
        ValidationAnnotation.event_type == request.event_type,
        ValidationAnnotation.split == request.split,
        ValidationAnnotation.ground_truth_label == "positive",
    )).all()
    annotations_total = db.scalar(select(func.count()).select_from(ValidationAnnotation).where(
        ValidationAnnotation.video_id == video_id,
        ValidationAnnotation.event_type == request.event_type,
        ValidationAnnotation.split == request.split,
    )) or 0
    predictions = db.scalars(select(CandidateEvent).where(
        CandidateEvent.video_id == video_id,
        CandidateEvent.event_type == request.event_type,
        CandidateEvent.synthetic_fixture.is_(False),
    )).all()
    result = evaluate_events(
        [IntervalEvent(item.id, item.start_seconds, item.end_seconds, item.event_type) for item in predictions],
        [IntervalEvent(item.id, item.start_seconds, item.end_seconds, item.event_type) for item in positives],
        request.temporal_iou_threshold, request.onset_tolerance_seconds,
    )
    return {**result, "video_id": video_id, "event_type": request.event_type, "split": request.split, "annotations_total": annotations_total, "positive_annotations": len(positives), "prediction_count": len(predictions), "warning": "Metrics describe only this annotated local set and are not evidence of generalization."}


@app.post("/api/datasets/assets", response_model=DatasetAssetOut, status_code=201)
def register_dataset_asset(request: DatasetAssetCreate, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "reviewer"))):
    video = db.get(Video, request.video_id)
    if not video:
        raise HTTPException(404, "video not found")
    authorize_video(db, actor, video, "manage")
    organization = db.get(Organization, video.organization_id)
    if not organization or organization.workspace_type != "research":
        raise HTTPException(403, "research datasets may only be registered in research workspaces")
    deterministic_id = "ds-" + hashlib.sha256(
        f"{request.dataset_name}|{request.original_recording_id}".encode("utf-8")
    ).hexdigest()[:32]
    existing = db.scalar(select(DatasetAsset).where(
        DatasetAsset.dataset_name == request.dataset_name,
        DatasetAsset.original_recording_id == request.original_recording_id,
    ))
    if existing:
        if existing.video_id != request.video_id:
            raise HTTPException(409, detail={"code": "dataset_record_already_imported", "video_id": existing.video_id})
        existing.evaluation_label = request.evaluation_label
        existing.detailed_label = request.detailed_label
        existing.source_url = request.source_url
        existing.source_license = request.source_license
        existing.annotation_status = request.annotation_status
        existing.manifest_record_json = json.dumps(request.manifest_record, sort_keys=True)
        db.commit()
        return DatasetAssetOut(
            id=existing.id, video_id=existing.video_id, dataset_name=existing.dataset_name,
            original_recording_id=existing.original_recording_id, evaluation_label=existing.evaluation_label,
            detailed_label=existing.detailed_label, source_url=existing.source_url,
            source_license=existing.source_license, annotation_status=existing.annotation_status,
            manifest_record=json.loads(existing.manifest_record_json), imported_at=existing.imported_at,
        )
    asset = DatasetAsset(
        id=deterministic_id, video_id=request.video_id, dataset_name=request.dataset_name,
        original_recording_id=request.original_recording_id, evaluation_label=request.evaluation_label,
        detailed_label=request.detailed_label, source_url=request.source_url,
        source_license=request.source_license, annotation_status=request.annotation_status,
        manifest_record_json=json.dumps(request.manifest_record, sort_keys=True),
    )
    db.add(asset); db.commit()
    return DatasetAssetOut(**request.model_dump(), id=asset.id, imported_at=asset.imported_at)


@app.get("/api/datasets/assets")
def list_dataset_assets(dataset_name: str | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    statement = select(DatasetAsset).where(DatasetAsset.video_id.in_(accessible_video_ids(db, user))).order_by(DatasetAsset.dataset_name, DatasetAsset.original_recording_id)
    if dataset_name:
        statement = statement.where(DatasetAsset.dataset_name == dataset_name)
    return [dataset_asset_dict(asset, db) for asset in db.scalars(statement).all()]


@app.get("/api/datasets/summary")
def dataset_summary(db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer"))):
    assets = db.scalars(select(DatasetAsset).where(DatasetAsset.video_id.in_(accessible_video_ids(db, user)))).all()
    names = sorted({asset.dataset_name for asset in assets})
    return {
        "datasets": [{
            "name": name,
            "videos": sum(asset.dataset_name == name for asset in assets),
            "falls": sum(asset.dataset_name == name and asset.evaluation_label == "fall" for asset in assets),
            "non_falls": sum(asset.dataset_name == name and asset.evaluation_label == "non_fall" for asset in assets),
            "license": next(asset.source_license for asset in assets if asset.dataset_name == name),
            "source_url": next(asset.source_url for asset in assets if asset.dataset_name == name),
        } for name in names],
        "total_videos": len(assets),
    }


@app.get("/api/datasets/assets/{asset_id}/diagnostics")
def dataset_asset_diagnostics(asset_id: str, db: Session = Depends(get_db)):
    dataset_asset = db.get(DatasetAsset, asset_id)
    if not dataset_asset:
        raise HTTPException(404, "dataset asset not found")
    rows = db.scalars(select(PoseEvidence).where(
        PoseEvidence.video_id == dataset_asset.video_id
    ).order_by(PoseEvidence.timestamp_seconds)).all()
    observations = [
        observation_from_landmarks(row.timestamp_seconds, row.frame_id, json.loads(row.landmarks_json))
        for row in rows
    ]
    series = diagnostic_series(observations)
    for point in series:
        point["image_url"] = f"/api/frames/{point['frame_id']}/image"
        point["overlay_url"] = f"/api/frames/{point['frame_id']}/overlay"
    annotations = db.scalars(select(ValidationAnnotation).where(
        ValidationAnnotation.video_id == dataset_asset.video_id,
        ValidationAnnotation.event_type == "potential_fall",
    ).order_by(ValidationAnnotation.start_seconds)).all()
    stored = db.scalars(select(CandidateEvent).where(
        CandidateEvent.video_id == dataset_asset.video_id,
        CandidateEvent.event_type == "potential_fall",
        CandidateEvent.synthetic_fixture.is_(False),
    ).order_by(CandidateEvent.start_seconds)).all()
    return {
        "asset_id": dataset_asset.id,
        "record_id": dataset_asset.original_recording_id,
        "video_id": dataset_asset.video_id,
        "ground_truth": dataset_asset.evaluation_label,
        "annotation_status": dataset_asset.annotation_status,
        "summary": summarize_diagnostics(series),
        "timeline": series,
        "source_intervals": [{
            "id": item.id, "start_seconds": item.start_seconds, "end_seconds": item.end_seconds,
            "label": item.ground_truth_label, "source": item.annotation_source,
        } for item in annotations],
        "stored_baseline_events": [event_dict(item) for item in stored],
        "profiles": {
            "baseline": {"thresholds": BASELINE_PROFILE, "events": run_profile(observations, BASELINE_PROFILE)},
            "improved": {"thresholds": IMPROVED_PROFILE, "events": run_profile(observations, IMPROVED_PROFILE)},
            "motion_fusion": {"thresholds": MOTION_FUSION_PROFILE, "events": [event.__dict__ for event in detect_motion_fusion_events(observations, **{key: value for key, value in MOTION_FUSION_PROFILE.items() if key != "name"})]},
        },
        "warning": "Plots are measured pose outputs. Source intervals are annotations; profile events are deterministic replay, not calibrated probabilities.",
    }


ORIGINAL_UR_BASELINE_IDS = {
    *(f"fall-{number:02d}" for number in (2, 7, 18, 19, 20, 22, 23, 24, 25, 26)),
    *(f"adl-{number:02d}" for number in (1, 3, 10, 14, 15, 17, 19, 30, 32, 35)),
}


@app.get("/api/datasets/evaluation")
def dataset_evaluation(
    dataset_name: str | None = None,
    completed_only: bool = True,
    cohort: str | None = None,
    db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "reviewer")),
):
    statement = select(DatasetAsset).where(DatasetAsset.video_id.in_(accessible_video_ids(db, user))).order_by(DatasetAsset.original_recording_id)
    if dataset_name:
        statement = statement.where(DatasetAsset.dataset_name == dataset_name)
    if cohort == "original_20":
        statement = statement.where(DatasetAsset.original_recording_id.in_(ORIGINAL_UR_BASELINE_IDS))
    elif cohort is not None:
        raise HTTPException(422, "cohort must be original_20 when supplied")
    assets = db.scalars(statement).all()
    rows = []
    predictions = []
    for asset in assets:
        video = db.get(Video, asset.video_id)
        latest_job = db.scalar(select(ProcessingJob).where(ProcessingJob.video_id == asset.video_id).order_by(ProcessingJob.created_at.desc()))
        if completed_only and (not latest_job or latest_job.status != "completed"):
            continue
        events = db.scalars(select(CandidateEvent).where(
            CandidateEvent.video_id == asset.video_id,
            CandidateEvent.event_type == "potential_fall",
            CandidateEvent.synthetic_fixture.is_(False),
        ).order_by(CandidateEvent.start_seconds)).all()
        prediction = VideoPrediction(asset.original_recording_id, asset.evaluation_label, bool(events), len(events))
        predictions.append(prediction)
        rows.append({
            "asset_id": asset.id, "record_id": asset.original_recording_id, "video_id": asset.video_id,
            "ground_truth": asset.evaluation_label, "predicted_fall": bool(events),
            "event_count": len(events), "candidate_timestamps": [event.start_seconds for event in events],
            "processing_status": latest_job.status if latest_job else "not_started",
            "processing_metrics": json.loads(latest_job.metrics_json) if latest_job and latest_job.metrics_json else {},
            "duration_seconds": video.duration_seconds if video else None,
            "annotation_status": asset.annotation_status,
        })
    return {
        "dataset_name": "UR original 20 baseline" if cohort == "original_20" else dataset_name or "all imported datasets",
        "cohort": cohort or "all",
        "protocol": "video-level: any non-synthetic potential_fall candidate counts as a positive prediction",
        "metrics": evaluate_video_predictions(predictions), "records": rows,
        "event_level_warning": "Event-level metrics require verified temporal annotations and are not inferred from video-level labels.",
    }


@app.patch("/api/events/{event_id}/review")
def review_event(event_id: str, body: ReviewUpdate, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "reviewer"))):
    event = db.get(CandidateEvent, event_id)
    if not event:
        raise HTTPException(404, "event not found")
    event.review_status = body.status
    event.reviewer_note = body.reviewer_note
    event.reviewer_id = actor.id
    event.reviewed_at = now_iso()
    video = db.get(Video, event.video_id)
    record_audit(db, request, "incident.review_changed", "success", actor=actor, organization_id=video.organization_id if video else None, object_type="candidate_event", object_id=event.id, metadata={"status": body.status})
    db.commit()
    return event_dict(event)


@app.post("/api/events/{event_id}/export", status_code=201)
def export_event(event_id: str, body: ExportRequest, request: Request, db: Session = Depends(get_db), actor: User = Depends(require_roles("admin", "reviewer"))):
    event = db.get(CandidateEvent, event_id)
    if not event:
        raise HTTPException(404, "event not found")
    video = db.get(Video, event.video_id)
    clip_id = str(uuid4())
    destination = safe_within(settings.exports_dir / video.organization_id / video.site_id / f"{clip_id}.mp4", settings.exports_dir)
    destination.parent.mkdir(parents=True, exist_ok=True)
    elapsed = export_clip(Path(video.path), destination, body.start_seconds, body.end_seconds, video.duration_seconds or 0)
    clip = ExportedClip(id=clip_id, video_id=video.id, event_id=event.id, path=str(destination), start_seconds=body.start_seconds, end_seconds=body.end_seconds, duration_seconds=body.end_seconds - body.start_seconds, created_by_user_id=actor.id)
    db.add(clip)
    record_audit(db, request, "evidence.exported", "success", actor=actor, organization_id=video.organization_id, object_type="exported_clip", object_id=clip.id, metadata={"event_id": event.id})
    db.commit()
    return {"id": clip.id, "download_url": f"/api/exports/{clip.id}/download", "export_seconds": elapsed}


@app.get("/api/exports/{clip_id}/download")
def download_export(clip_id: str, db: Session = Depends(get_db)):
    clip = db.get(ExportedClip, clip_id)
    if not clip:
        raise HTTPException(404, "export not found")
    return FileResponse(safe_within(Path(clip.path), settings.exports_dir), media_type="video/mp4", filename=f"visionguard-{clip.id}.mp4")


@app.get("/api/system/info")
def system_info():
    return {
        "mode": "Controlled offline research — human review required",
        "python_backend_version": __version__, "pytorch": torch.__version__,
        "torchvision": torchvision.__version__, "mediapipe": mediapipe.__version__,
        "cuda_available": torch.cuda.is_available(), "cuda_runtime": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "gpu_memory_total_mib": torch.cuda.get_device_properties(0).total_memory / 2**20 if torch.cuda.is_available() else None,
        "models": [
            {"name": clip_engine.model_name, "loaded": clip_engine.model is not None, "device": str(clip_engine.device), "purpose": "semantic retrieval"},
            {**object_detector.metadata.to_dict(), "name": object_detector.model_name, "loaded": object_detector.model is not None, "purpose": "COCO object detection"},
            {"name": pose_engine.model_name, "loaded": pose_engine.landmarker is not None, "device": "MediaPipe runtime", "purpose": "pose landmarks"},
        ],
        "limitations": [
            "Similarity scores are not calibrated probabilities.",
            "Safety candidates require explicit human review.",
            "No facial recognition, identity tracking, or criminal-intent inference.",
            "Not certified for safety-critical or surveillance deployment.",
        ],
    }
