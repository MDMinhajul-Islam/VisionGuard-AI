from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import ALGORITHM, AUDIENCE, ISSUER, SESSION_COOKIE, hash_password
from app.database.models import (
    AuditEvent, AuthSession, CandidateEvent, DatasetAsset, ExportedClip, Organization,
    OrganizationMembership, ProcessingJob, Site, SiteAccess, User, Video, VideoFrame,
)
from app.database.session import SessionLocal, init_db
from app.main import app


PASSWORD = "tenant-test-password-123!"
ORIGIN = "http://localhost:3000"


def create_tenant(label: str, *, global_role: str = "reviewer", membership_role: str = "safety_reviewer") -> dict[str, str]:
    init_db()
    suffix = uuid4().hex[:10]
    with SessionLocal() as db:
        organization = Organization(name=f"{label} {suffix}", workspace_type="research")
        db.add(organization); db.flush()
        site = Site(organization_id=organization.id, name=f"{label} Site")
        user = User(email=f"{label.lower()}-{suffix}@test.local", display_name=label, password_hash=hash_password(PASSWORD), role=global_role)
        db.add_all([site, user]); db.flush()
        membership = OrganizationMembership(user_id=user.id, organization_id=organization.id, role=membership_role)
        db.add(membership); db.flush(); db.add(SiteAccess(membership_id=membership.id, site_id=site.id))
        video = Video(organization_id=organization.id, site_id=site.id, original_filename=f"{label}.mp4", stored_filename=f"{suffix}.mp4", path=f"{suffix}.mp4", size_bytes=10, duration_seconds=10, status="indexed")
        db.add(video); db.flush()
        frame = VideoFrame(video_id=video.id, timestamp_seconds=1, frame_number=1, path=f"{suffix}.jpg", width=640, height=360)
        event = CandidateEvent(video_id=video.id, event_type="potential_fall", label="Potential Fall — Review Required", start_seconds=1, end_seconds=2, processing_method="test", model_version="test", raw_scores_json="{}", thresholds_json="{}", supporting_frames_json="[]")
        job = ProcessingJob(video_id=video.id, status="completed")
        db.add_all([frame, event, job]); db.flush()
        clip = ExportedClip(video_id=video.id, event_id=event.id, path=f"{suffix}-clip.mp4", start_seconds=1, end_seconds=2, duration_seconds=1)
        asset = DatasetAsset(id=f"asset-{suffix}", video_id=video.id, dataset_name=f"Research {label}", original_recording_id=suffix, evaluation_label="fall", source_url="https://example.edu/research", source_license="research only", annotation_status="video_level_only")
        db.add_all([clip, asset]); db.commit()
        return {"user_id": user.id, "email": user.email, "organization_id": organization.id, "site_id": site.id, "membership_id": membership.id, "video_id": video.id, "frame_id": frame.id, "event_id": event.id, "job_id": job.id, "clip_id": clip.id, "asset_id": asset.id}


def login_client(tenant: dict[str, str]) -> TestClient:
    client = TestClient(app)
    client.__enter__()
    client.headers["Origin"] = ORIGIN
    response = client.post("/api/auth/login", json={"email": tenant["email"], "password": PASSWORD})
    assert response.status_code == 200
    return client


def test_cross_organization_objects_and_collections_are_isolated():
    tenant_a = create_tenant("Tenant A")
    tenant_b = create_tenant("Tenant B")
    client = login_client(tenant_a)
    try:
        listed = client.get("/api/videos").json()
        assert {item["id"] for item in listed} == {tenant_a["video_id"]}
        assert client.get(f"/api/videos/{tenant_b['video_id']}").status_code == 404
        assert client.get(f"/api/videos/{tenant_b['video_id']}/media").status_code == 404
        assert client.get(f"/api/videos/{tenant_b['video_id']}/analysis-timeline").status_code == 404
        assert client.get(f"/api/frames/{tenant_b['frame_id']}/image").status_code == 404
        assert client.get(f"/api/events/{tenant_b['event_id']}/evidence").status_code == 404
        assert client.get(f"/api/jobs/{tenant_b['job_id']}").status_code == 404
        assert client.get(f"/api/exports/{tenant_b['clip_id']}/download").status_code == 404
        assert client.get(f"/api/datasets/assets/{tenant_b['asset_id']}/diagnostics").status_code == 404
        assert client.patch(f"/api/events/{tenant_b['event_id']}/review", json={"status": "false_positive", "reviewer_note": "attack"}).status_code == 404
        assert client.post(f"/api/events/{tenant_b['event_id']}/export", json={"start_seconds": 1, "end_seconds": 2}).status_code == 404
        assert client.post(f"/api/videos/{tenant_b['video_id']}/search", json={"query": "person falling"}).status_code == 404
        assert client.get("/api/frames/%2e%2e%2fprivate/image").status_code in {400, 404}
        dataset_rows = client.get("/api/datasets/assets").json()
        assert {item["id"] for item in dataset_rows} == {tenant_a["asset_id"]}
        timeline = client.get(f"/api/videos/{tenant_a['video_id']}/analysis-timeline").json()
        assert timeline["video"]["id"] == tenant_a["video_id"]
        assert timeline["provenance"]["detector_architecture"] == "SSDLite320 MobileNetV3 Large"
        assert timeline["provenance"]["note"].startswith("Only stored sampled inference")
        with SessionLocal() as db:
            denied = db.scalar(select(AuditEvent).where(AuditEvent.action == "authorization.object_access", AuditEvent.outcome == "denied", AuditEvent.organization_id == tenant_b["organization_id"]))
            assert denied is not None
    finally:
        client.__exit__(None, None, None)


def test_review_creates_scoped_audit_record_and_role_change_is_immediate():
    tenant = create_tenant("Audit Tenant")
    client = login_client(tenant)
    try:
        response = client.patch(f"/api/events/{tenant['event_id']}/review", json={"status": "false_positive", "reviewer_note": "Verified by reviewer"})
        assert response.status_code == 200
        with SessionLocal() as db:
            audit = db.scalar(select(AuditEvent).where(AuditEvent.action == "incident.review_changed", AuditEvent.object_id == tenant["event_id"]))
            assert audit and audit.organization_id == tenant["organization_id"] and audit.outcome == "success"
            membership = db.get(OrganizationMembership, tenant["membership_id"])
            membership.role = "read_only_auditor"; db.commit()
        assert client.patch(f"/api/events/{tenant['event_id']}/review", json={"status": "pending", "reviewer_note": "unauthorized"}).status_code == 404
        assert client.get(f"/api/events/{tenant['event_id']}").status_code == 200
    finally:
        client.__exit__(None, None, None)


def test_logout_revokes_server_session_and_disabled_user_is_rejected():
    tenant = create_tenant("Session Tenant")
    client = login_client(tenant)
    token = client.cookies.get(SESSION_COOKIE)
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    client.__exit__(None, None, None)
    with TestClient(app) as replay:
        replay.cookies.set(SESSION_COOKIE, token)
        assert replay.get("/api/auth/me").status_code == 401

    second = login_client(tenant)
    try:
        with SessionLocal() as db:
            user = db.get(User, tenant["user_id"]); user.disabled = True; db.commit()
        assert second.get("/api/auth/me").status_code == 401
    finally:
        second.__exit__(None, None, None)


def test_expired_session_csrf_and_login_rate_limit():
    tenant = create_tenant("Expired Tenant")
    now = datetime.now(timezone.utc)
    jti = str(uuid4())
    payload = {"sub": tenant["user_id"], "role": "reviewer", "iss": ISSUER, "aud": AUDIENCE, "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1), "jti": jti, "sv": 0}
    token = jwt.encode(payload, get_settings().effective_auth_secret(), algorithm=ALGORITHM)
    with SessionLocal() as db:
        db.add(AuthSession(jti=jti, user_id=tenant["user_id"], session_version=0, expires_at=(now - timedelta(hours=1)).isoformat())); db.commit()
    with TestClient(app) as expired:
        expired.cookies.set(SESSION_COOKIE, token)
        assert expired.get("/api/auth/me").status_code == 401

    client = login_client(tenant)
    try:
        client.headers.pop("Origin")
        assert client.post("/api/auth/logout").status_code == 403
    finally:
        client.__exit__(None, None, None)

    unknown = f"missing-{uuid4().hex}@test.local"
    with TestClient(app) as attempts:
        statuses = [attempts.post("/api/auth/login", json={"email": unknown, "password": PASSWORD}).status_code for _ in range(get_settings().login_rate_limit_attempts + 1)]
    assert statuses[-1] == 429
    assert all(status == 401 for status in statuses[:-1])


def test_password_change_revokes_the_current_and_all_other_sessions():
    tenant = create_tenant("Password Tenant")
    client = login_client(tenant)
    try:
        response = client.post("/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "replacement-password-456!"})
        assert response.status_code == 204
        assert client.get("/api/auth/me").status_code == 401
    finally:
        client.__exit__(None, None, None)


def test_site_administrator_can_manage_only_an_explicitly_granted_site():
    tenant = create_tenant("Site Admin Tenant", membership_role="site_admin")
    client = login_client(tenant)
    try:
        response = client.post(f"/api/videos/{tenant['video_id']}/zones", json={"name": "Keep Clear", "polygon": [[0.1, 0.1], [0.8, 0.1], [0.8, 0.8]]})
        assert response.status_code == 201
    finally:
        client.__exit__(None, None, None)
