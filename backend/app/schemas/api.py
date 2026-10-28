from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ReviewStatus = Literal["pending", "confirmed_by_reviewer", "false_positive", "needs_further_review"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VideoOut(ORMModel):
    id: str
    original_filename: str
    size_bytes: int
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    codec: str | None
    status: str
    is_demo: bool
    created_at: str
    thumbnail_url: str | None = None
    media_url: str | None = None


class ProcessRequest(BaseModel):
    clip_sample_seconds: float = Field(default=1.0, ge=0.2, le=30)
    analysis_fps: float = Field(default=2.0, ge=0.2, le=15)
    pose_fps: float = Field(default=5.0, ge=1, le=15)
    process_width: int = Field(default=640, ge=224, le=1280)
    detection_threshold: float = Field(default=0.45, ge=0.05, le=0.99)
    enable_clip: bool = True
    enable_detection: bool = True
    enable_pose: bool = True


class JobOut(ORMModel):
    id: str
    video_id: str
    status: str
    progress: float
    stage: str
    config_json: str
    metrics_json: str
    error: str | None
    cancel_requested: bool
    created_at: str
    started_at: str | None
    completed_at: str | None


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=50)
    temporal_suppression_seconds: float = Field(default=2.0, ge=0, le=30)


class SearchResult(BaseModel):
    frame_id: str
    timestamp_seconds: float
    similarity: float
    preview_url: str


class SearchResponse(BaseModel):
    query: str
    model: str
    score_warning: str
    elapsed_ms: float
    results: list[SearchResult]


class ZoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    zone_type: Literal["emergency_exit", "walkway"] = "emergency_exit"
    polygon: list[tuple[float, float]] = Field(min_length=3, max_length=20)

    @model_validator(mode="after")
    def valid_normalized_polygon(self):
        if any(not (0 <= x <= 1 and 0 <= y <= 1) for x, y in self.polygon):
            raise ValueError("polygon coordinates must be normalized to [0, 1]")
        area = sum(
            self.polygon[i][0] * self.polygon[(i + 1) % len(self.polygon)][1]
            - self.polygon[(i + 1) % len(self.polygon)][0] * self.polygon[i][1]
            for i in range(len(self.polygon))
        ) / 2
        if abs(area) < 1e-5:
            raise ValueError("polygon must have non-zero area")
        return self


class ReviewUpdate(BaseModel):
    status: ReviewStatus
    reviewer_note: str = Field(default="", max_length=4000)


class ExportRequest(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def end_after_start(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        if self.end_seconds - self.start_seconds > 300:
            raise ValueError("clips are limited to five minutes")
        return self

