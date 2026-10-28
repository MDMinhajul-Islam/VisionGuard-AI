from __future__ import annotations

import threading
import time

import cv2
import torch
from torchvision.models.detection import (
    SSDLite320_MobileNet_V3_Large_Weights,
    ssdlite320_mobilenet_v3_large,
)

from app.core.config import get_settings


class ObjectDetector:
    model_name = "torchvision-ssdlite320-mobilenet-v3-large-coco-v1"

    def __init__(self):
        settings = get_settings()
        self.device = torch.device("cuda" if settings.device == "auto" and torch.cuda.is_available() else settings.device if settings.device != "auto" else "cpu")
        self.model = None
        self.transforms = None
        self.categories = None
        self._lock = threading.Lock()
        self.last_inference_ms = None

    def load(self):
        if self.model is None:
            with self._lock:
                if self.model is None:
                    # Keep official weights in project-local ignored storage, not a global cache.
                    torch.hub.set_dir(str(get_settings().model_dir / "torch"))
                    weights = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
                    self.model = ssdlite320_mobilenet_v3_large(weights=weights).to(self.device).eval()
                    self.transforms = weights.transforms()
                    self.categories = weights.meta["categories"]

    @torch.inference_mode()
    def detect(self, frame, threshold=0.45, allowed_labels=None):
        self.load()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = torch.from_numpy(rgb).permute(2, 0, 1)
        input_tensor = self.transforms(tensor).to(self.device)
        if self.device.type == "cuda":
            torch.cuda.synchronize()
        started = time.perf_counter()
        with self._lock:
            prediction = self.model([input_tensor])[0]
        if self.device.type == "cuda":
            torch.cuda.synchronize()
        self.last_inference_ms = (time.perf_counter() - started) * 1000
        height, width = frame.shape[:2]
        results = []
        for box, label_id, score in zip(prediction["boxes"].cpu(), prediction["labels"].cpu(), prediction["scores"].cpu()):
            confidence = float(score)
            if confidence < threshold:
                continue
            label = self.categories[int(label_id)]
            if allowed_labels and label not in allowed_labels:
                continue
            x1, y1, x2, y2 = (float(value) for value in box)
            results.append({
                "label": label,
                "confidence": confidence,
                "bbox_pixels": (x1, y1, x2, y2),
                "bbox": (x1 / width, y1 / height, x2 / width, y2 / height),
            })
        return results

    def unload(self):
        with self._lock:
            self.model = self.transforms = self.categories = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


object_detector = ObjectDetector()

