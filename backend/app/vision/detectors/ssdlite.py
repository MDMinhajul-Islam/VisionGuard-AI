from __future__ import annotations

import numpy as np

from app.vision.detectors.base import DetectionRecord, DetectorMetadata, validate_detections
from app.vision.object_detector import ObjectDetector


class SSDLiteAdapter:
    """Commercial-candidate adapter around the preserved Torchvision detector."""

    def __init__(self):
        self.engine = ObjectDetector()

    @property
    def metadata(self) -> DetectorMetadata:
        return DetectorMetadata(
            model_id=self.engine.model_name,
            model_version="COCO_V1",
            architecture="SSDLite320 MobileNetV3 Large",
            checkpoint=self.engine.metadata.checkpoint,
            license="Torchvision BSD-3-Clause; checkpoint/training-data provenance requires release review",
            commercial_runtime_eligible=False,
            device=str(self.engine.device),
            class_names=tuple(self.engine.categories or ()),
        )

    @property
    def last_inference_ms(self) -> float | None:
        return self.engine.last_inference_ms

    def load(self) -> None:
        self.engine.load()

    def detect(self, frame: np.ndarray, threshold: float = 0.45, allowed_labels: set[str] | None = None) -> list[DetectionRecord]:
        detections = self.engine.detect(frame, threshold, allowed_labels)
        for item in detections:
            item.update({
                "model_id": self.engine.model_name,
                "model_version": "COCO_V1",
                "device": str(self.engine.device),
                "provenance": "torchvision:ssdlite320_mobilenet_v3_large:COCO_V1",
            })
        validate_detections(detections)
        return detections

    def unload(self) -> None:
        self.engine.unload()
