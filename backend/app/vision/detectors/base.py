from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol, TypedDict

import numpy as np


class DetectionRecord(TypedDict):
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]
    bbox_pixels: tuple[float, float, float, float]
    model_id: str
    model_version: str
    device: str
    provenance: str


@dataclass(frozen=True)
class DetectorMetadata:
    model_id: str
    model_version: str
    architecture: str
    checkpoint: str
    license: str
    commercial_runtime_eligible: bool
    device: str
    class_names: tuple[str, ...]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["class_names"] = list(self.class_names)
        return payload


class DetectorAdapter(Protocol):
    @property
    def metadata(self) -> DetectorMetadata: ...

    @property
    def last_inference_ms(self) -> float | None: ...

    def load(self) -> None: ...

    def detect(self, frame: np.ndarray, threshold: float = 0.45, allowed_labels: set[str] | None = None) -> list[DetectionRecord]: ...

    def unload(self) -> None: ...


def validate_detections(detections: list[DetectionRecord]) -> None:
    for item in detections:
        if not 0 <= item["confidence"] <= 1:
            raise ValueError("detector confidence must be within [0, 1]")
        x1, y1, x2, y2 = item["bbox"]
        if not (0 <= x1 <= x2 <= 1 and 0 <= y1 <= y2 <= 1):
            raise ValueError("normalized detector box must be ordered within [0, 1]")
        if not item["label"] or not item["model_id"] or not item["provenance"]:
            raise ValueError("detection identity and provenance are required")
