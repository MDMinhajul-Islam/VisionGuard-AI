from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ExperimentRecord(BaseModel):
    experiment_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    registry: Literal["research", "commercial_candidate", "released"]
    dataset_id: str
    dataset_source: str
    dataset_license: str
    manifest_version: str
    model_architecture: str
    checkpoint_identity: str
    checkpoint_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    model_license: str
    configuration: dict
    evaluation_protocol: dict
    hardware: dict
    runtime_versions: dict
    measured_results: dict
    git_commit: str = Field(min_length=7, max_length=40)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_by: str | None = None

    def enforce_release_gate(self) -> None:
        if self.registry == "released" and not self.approved_by:
            raise ValueError("released models require an explicit human approver")


def write_experiment_record(record: ExperimentRecord, root: Path) -> Path:
    record.enforce_release_gate()
    destination = root / record.registry / f"{record.experiment_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, destination)
    return destination
