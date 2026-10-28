from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.schemas.api import AnnotationCreate


def deterministic_annotation_id(annotation: AnnotationCreate) -> str:
    payload = annotation.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "ann_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


class ValidationManifest(BaseModel):
    dataset_name: str = Field(min_length=1, max_length=200)
    provenance: str = Field(min_length=3, max_length=2000)
    license_or_consent: str = Field(min_length=3, max_length=1000)
    exhaustive_annotations: bool = False
    annotations: list[AnnotationCreate]

    @model_validator(mode="after")
    def unique_annotations(self):
        identifiers = [deterministic_annotation_id(item) for item in self.annotations]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("manifest contains duplicate annotations")
        return self


def load_manifest(path: Path) -> ValidationManifest:
    return ValidationManifest.model_validate_json(path.read_text(encoding="utf-8"))
