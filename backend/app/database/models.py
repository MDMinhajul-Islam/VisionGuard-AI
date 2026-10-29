from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def uid() -> str:
    return str(uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    path: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(100), default="video/mp4")
    size_bytes: Mapped[int] = mapped_column(Integer)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="uploaded", index=True)
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    jobs: Mapped[list["ProcessingJob"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(24), index=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    session_version: Mapped[int] = mapped_column(Integer, default=0)
    password_changed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    workspace_type: Mapped[str] = mapped_column(String(32), default="commercial_candidate", index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)


class Site(Base):
    __tablename__ = "sites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_site_organization_name"),)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),)


class SiteAccess(Base):
    __tablename__ = "site_access"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    membership_id: Mapped[str] = mapped_column(ForeignKey("organization_memberships.id", ondelete="CASCADE"), index=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    __table_args__ = (UniqueConstraint("membership_id", "site_id", name="uq_site_access_membership_site"),)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[str] = mapped_column(String(40), index=True)
    revoked_at: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    organization_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    object_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    outcome: Mapped[str] = mapped_column(String(24), index=True)
    request_id: Mapped[str] = mapped_column(String(36), index=True)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso, index=True)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0)
    stage: Mapped[str] = mapped_column(String(80), default="queued")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)
    started_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    video: Mapped[Video] = relationship(back_populates="jobs")


class VideoFrame(Base):
    __tablename__ = "video_frames"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float, index=True)
    frame_number: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(Text)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    clip_indexed: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_frames_video_time", "video_id", "timestamp_seconds"),)


class ObjectDetection(Base):
    __tablename__ = "object_detections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    frame_id: Mapped[str] = mapped_column(ForeignKey("video_frames.id", ondelete="CASCADE"), index=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float, index=True)
    label: Mapped[str] = mapped_column(String(80), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    bbox_json: Mapped[str] = mapped_column(Text)
    track_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class PoseEvidence(Base):
    __tablename__ = "pose_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    frame_id: Mapped[str] = mapped_column(ForeignKey("video_frames.id", ondelete="CASCADE"), index=True)
    timestamp_seconds: Mapped[float] = mapped_column(Float, index=True)
    frame_timestamp_seconds: Mapped[float] = mapped_column(Float)
    sync_error_seconds: Mapped[float] = mapped_column(Float)
    landmarks_json: Mapped[str] = mapped_column(Text, default="[]")
    signals_json: Mapped[str] = mapped_column(Text, default="{}")
    sufficient_evidence: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    __table_args__ = (Index("ix_pose_video_time", "video_id", "timestamp_seconds"),)


class SafetyZone(Base):
    __tablename__ = "safety_zones"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    zone_type: Mapped[str] = mapped_column(String(50), default="emergency_exit")
    polygon_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)


class CandidateEvent(Base):
    __tablename__ = "candidate_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    label: Mapped[str] = mapped_column(String(160))
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    processing_method: Mapped[str] = mapped_column(String(120))
    model_version: Mapped[str] = mapped_column(String(160))
    raw_scores_json: Mapped[str] = mapped_column(Text, default="{}")
    thresholds_json: Mapped[str] = mapped_column(Text, default="{}")
    supporting_frames_json: Mapped[str] = mapped_column(Text, default="[]")
    review_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    reviewer_note: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    synthetic_fixture: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)


class EmbeddingCache(Base):
    __tablename__ = "embedding_caches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True)
    path: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(String(120))
    frame_count: Mapped[int] = mapped_column(Integer)
    dimensions: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)


class ExportedClip(Base):
    __tablename__ = "exported_clips"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("candidate_events.id", ondelete="SET NULL"), nullable=True)
    path: Mapped[str] = mapped_column(Text)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    duration_seconds: Mapped[float] = mapped_column(Float)
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)


class ValidationAnnotation(Base):
    """Ground truth is intentionally separate from model-created CandidateEvent rows."""

    __tablename__ = "validation_annotations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    ground_truth_label: Mapped[str] = mapped_column(String(24), index=True)
    annotation_source: Mapped[str] = mapped_column(String(200))
    reviewer_note: Mapped[str] = mapped_column(Text, default="")
    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    split: Mapped[str] = mapped_column(String(24), default="evaluation", index=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now_iso)

    __table_args__ = (
        UniqueConstraint("video_id", "event_type", "start_seconds", "end_seconds", "ground_truth_label", "annotation_source", "query_text", name="uq_validation_annotation"),
        Index("ix_annotation_video_type_time", "video_id", "event_type", "start_seconds"),
    )


class DatasetAsset(Base):
    __tablename__ = "dataset_assets"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True)
    dataset_name: Mapped[str] = mapped_column(String(160), index=True)
    original_recording_id: Mapped[str] = mapped_column(String(160), index=True)
    evaluation_label: Mapped[str] = mapped_column(String(24), index=True)
    detailed_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_license: Mapped[str] = mapped_column(Text)
    annotation_status: Mapped[str] = mapped_column(String(64))
    manifest_record_json: Mapped[str] = mapped_column(Text, default="{}")
    imported_at: Mapped[str] = mapped_column(String(40), default=now_iso)

    __table_args__ = (
        UniqueConstraint("dataset_name", "original_recording_id", name="uq_dataset_recording"),
    )

