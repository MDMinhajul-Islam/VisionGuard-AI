from __future__ import annotations

import re

from fastapi import HTTPException, Request
from sqlalchemy import select

from app.database.models import (
    CandidateEvent, DatasetAsset, ExportedClip, Organization, OrganizationMembership,
    ProcessingJob, Site, SiteAccess, User, ValidationAnnotation, Video, VideoFrame,
)
from app.database.session import SessionLocal


ORG_ROLES = {"organization_admin", "site_admin", "safety_reviewer", "read_only_auditor"}
PERMISSIONS = {
    "read": ORG_ROLES,
    "review": {"organization_admin", "site_admin", "safety_reviewer"},
    "manage": {"organization_admin", "site_admin"},
    "organization_admin": {"organization_admin"},
}


def _not_found() -> HTTPException:
    return HTTPException(404, "resource not found")


def membership_for(db, user_id: str, organization_id: str) -> OrganizationMembership | None:
    return db.scalar(select(OrganizationMembership).where(
        OrganizationMembership.user_id == user_id,
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.status == "active",
    ))


def has_site_access(db, membership: OrganizationMembership, site_id: str) -> bool:
    if membership.role == "organization_admin":
        return True
    return db.scalar(select(SiteAccess.id).where(
        SiteAccess.membership_id == membership.id,
        SiteAccess.site_id == site_id,
    )) is not None


def authorize_video(db, user: User, video: Video, permission: str = "read") -> OrganizationMembership:
    organization = db.get(Organization, video.organization_id)
    site = db.get(Site, video.site_id)
    if not organization or not site or organization.status in {"disabled", "suspended"} or site.status in {"disabled", "suspended"}:
        raise _not_found()
    membership = membership_for(db, user.id, video.organization_id)
    if not membership or membership.role not in PERMISSIONS[permission] or not has_site_access(db, membership, video.site_id):
        raise _not_found()
    return membership


def accessible_video_ids(db, user: User) -> select:
    org_admin_orgs = select(OrganizationMembership.organization_id).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "active",
        OrganizationMembership.role == "organization_admin",
    )
    granted_sites = select(SiteAccess.site_id).join(OrganizationMembership).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "active",
    )
    return select(Video.id).where(
        (Video.organization_id.in_(org_admin_orgs)) | (Video.site_id.in_(granted_sites))
    )


def resolve_scope(db, user: User, organization_id: str | None, site_id: str | None, permission: str = "read") -> tuple[Organization, Site, OrganizationMembership]:
    memberships = db.scalars(select(OrganizationMembership).where(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.status == "active",
    )).all()
    if organization_id:
        memberships = [item for item in memberships if item.organization_id == organization_id]
    candidates: list[tuple[Organization, Site, OrganizationMembership]] = []
    for membership in memberships:
        if membership.role not in PERMISSIONS[permission]:
            continue
        sites = db.scalars(select(Site).where(Site.organization_id == membership.organization_id)).all()
        for site in sites:
            if site_id and site.id != site_id:
                continue
            if site.status not in {"disabled", "suspended"} and has_site_access(db, membership, site.id):
                organization = db.get(Organization, membership.organization_id)
                if organization and organization.status not in {"disabled", "suspended"}:
                    candidates.append((organization, site, membership))
    if len(candidates) != 1:
        raise HTTPException(400 if candidates else 403, "select one authorized organization and site")
    return candidates[0]


def authorize_object_request(request: Request, user: User) -> None:
    path = request.url.path
    method = request.method
    permission = "read"
    if method in {"POST", "PATCH", "DELETE"}:
        permission = "manage"
    if re.match(r"^/api/events/[^/]+/(review|export)$", path):
        permission = "review"

    video_id = None
    with SessionLocal() as db:
        match = re.match(r"^/api/videos/([^/]+)", path)
        if match and match.group(1) == "upload":
            match = None
        if match:
            video_id = match.group(1)
        match = re.match(r"^/api/frames/([^/]+)", path)
        if match:
            frame = db.get(VideoFrame, match.group(1))
            video_id = frame.video_id if frame else None
        match = re.match(r"^/api/events/([^/]+)", path)
        if match:
            event = db.get(CandidateEvent, match.group(1))
            video_id = event.video_id if event else None
        match = re.match(r"^/api/jobs/([^/]+)", path)
        if match:
            job = db.get(ProcessingJob, match.group(1))
            video_id = job.video_id if job else None
        match = re.match(r"^/api/exports/([^/]+)", path)
        if match:
            clip = db.get(ExportedClip, match.group(1))
            video_id = clip.video_id if clip else None
        match = re.match(r"^/api/datasets/assets/([^/]+)", path)
        if match and match.group(1) not in {"summary"}:
            asset = db.get(DatasetAsset, match.group(1))
            video_id = asset.video_id if asset else None
        match = re.match(r"^/api/validation/annotations/([^/]+)", path)
        if match:
            annotation = db.get(ValidationAnnotation, match.group(1))
            video_id = annotation.video_id if annotation else None
        if video_id is not None:
            video = db.get(Video, video_id)
            if not video:
                raise _not_found()
            request.state.organization_id = video.organization_id
            request.state.site_id = video.site_id
            membership = authorize_video(db, user, video, permission)
            request.state.membership_role = membership.role
