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
    pose_confidence_threshold: float = Field(default=0.5, ge=0.1, le=0.99)
    fall_transition_window: float = Field(default=1.5, ge=0.2, le=5)
    fall_min_vertical_drop: float = Field(default=0.12, ge=0.01, le=0.8)
    fall_horizontal_persistence: float = Field(default=0.6, ge=0.2, le=10)
    pose_max_gap: float = Field(default=0.6, ge=0.1, le=3)
    pose_smoothing_window: int = Field(default=3, ge=1, le=9)
    zone_overlap_threshold: float = Field(default=0.15, ge=0.01, le=1)
    obstruction_persistence: float = Field(default=2.0, ge=0.2, le=60)
    obstruction_max_gap: float = Field(default=1.0, ge=0, le=10)
    event_merge_interval: float = Field(default=1.0, ge=0, le=30)
    profile_name: str = Field(default="baseline", min_length=1, max_length=60)
    allow_reprocess_reviewed: bool = False
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


class ZoneAnalysisRequest(BaseModel):
    min_zone_occupancy: float = Field(default=0.15, ge=0.01, le=1)
    min_duration: float = Field(default=2.0, ge=0.2, le=60)
    max_gap: float = Field(default=1.0, ge=0, le=10)
    event_merge_interval: float = Field(default=1.0, ge=0, le=30)
    profile_name: str = Field(default="baseline", min_length=1, max_length=60)


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


GroundTruthLabel = Literal["positive", "negative", "uncertain", "no_event"]
ValidationSplit = Literal["development", "calibration", "evaluation"]


class AnnotationCreate(BaseModel):
    video_id: str = Field(min_length=1, max_length=64)
    event_type: Literal["potential_fall", "potential_exit_obstruction", "potential_walkway_obstruction", "semantic_search"]
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    ground_truth_label: GroundTruthLabel
    annotation_source: str = Field(min_length=3, max_length=200)
    reviewer_note: str = Field(default="", max_length=4000)
    query_text: str | None = Field(default=None, max_length=500)
    split: ValidationSplit = "evaluation"

    @model_validator(mode="after")
    def validate_interval_and_query(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        if self.event_type == "semantic_search" and not self.query_text:
            raise ValueError("semantic_search annotations require query_text")
        return self


class AnnotationOut(AnnotationCreate):
    id: str
    created_at: str


class EvaluationRequest(BaseModel):
    event_type: Literal["potential_fall", "potential_exit_obstruction", "potential_walkway_obstruction"]
    split: ValidationSplit = "evaluation"
    temporal_iou_threshold: float = Field(default=0.3, ge=0, le=1)
    onset_tolerance_seconds: float = Field(default=1.0, ge=0, le=30)


class DatasetAssetCreate(BaseModel):
    video_id: str = Field(min_length=1, max_length=64)
    dataset_name: str = Field(min_length=2, max_length=160)
    original_recording_id: str = Field(min_length=1, max_length=160)
    evaluation_label: Literal["fall", "non_fall"]
    detailed_label: str | None = Field(default=None, max_length=120)
    source_url: str = Field(min_length=8, max_length=2000)
    source_license: str = Field(min_length=3, max_length=1000)
    annotation_status: Literal["video_level_only", "source_frame_labels", "human_temporal"]
    manifest_record: dict = Field(default_factory=dict)


class DatasetAssetOut(DatasetAssetCreate):
    id: str
    imported_at: str

