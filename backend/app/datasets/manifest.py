from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


EvaluationLabel = Literal["fall", "non_fall"]


class PreparedVideo(BaseModel):
    record_id: str = Field(min_length=3, max_length=160)
    source_dataset: str = Field(min_length=2, max_length=80)
    original_recording_id: str = Field(min_length=1, max_length=120)
    prepared_video_path: str = Field(min_length=1)
    original_label: str = Field(min_length=1, max_length=120)
    evaluation_label: EvaluationLabel
    detailed_label: str | None = Field(default=None, max_length=120)
    duration_seconds: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)
    frame_count: int = Field(gt=0)
    conversion_status: Literal["converted", "copied_compatible"]
    annotation_status: Literal["video_level_only", "source_frame_labels", "human_temporal"]
    source_url: str
    source_license: str
    source_archive_sha256: str
    prepared_sha256: str
    timing_source: str
    split: Literal["development", "calibration", "evaluation"] = "evaluation"


class PreparedManifest(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_name: str
    seed: int
    created_at: str
    records: list[PreparedVideo]

    @model_validator(mode="after")
    def unique_records(self):
        ids = [record.record_id for record in self.records]
        if len(ids) != len(set(ids)):
            raise ValueError("record_id values must be unique")
        paths = [record.prepared_video_path for record in self.records]
        if len(paths) != len(set(paths)):
            raise ValueError("prepared_video_path values must be unique")
        return self
