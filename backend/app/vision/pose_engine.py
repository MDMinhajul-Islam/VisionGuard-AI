from __future__ import annotations

import threading
import time
from pathlib import Path

import cv2
import numpy as np

from app.core.config import get_settings
from app.vision.fall_detection import PoseObservation


class PoseEngine:
    model_name = "MediaPipe Pose Landmarker Lite"

    def __init__(self):
        self.settings = get_settings()
        self.model_path = self.settings.model_dir / "pose_landmarker_lite.task"
        self.landmarker = None
        self._lock = threading.Lock()
        self.last_inference_ms = None

    def load(self):
        if self.landmarker is not None:
            return
        if not self.model_path.exists():
            raise FileNotFoundError(f"Pose model missing: {self.model_path}. Run scripts/setup_models.py")
        import mediapipe as mp
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(self.model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)

    def process(self, frame, timestamp_ms: int, frame_id="") -> PoseObservation:
        self.load()
        import mediapipe as mp
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        started = time.perf_counter()
        with self._lock:
            result = self.landmarker.detect_for_video(image, timestamp_ms)
        self.last_inference_ms = (time.perf_counter() - started) * 1000
        if not result.pose_landmarks:
            return PoseObservation(timestamp_ms / 1000, None, None, None, 0.0, frame_id, [], list(range(33)))
        points = result.pose_landmarks[0]
        ids = [11, 12, 23, 24, 27, 28]
        visibility = sum(float(points[index].visibility or 0) for index in ids) / len(ids)
        shoulder = ((points[11].x + points[12].x) / 2, (points[11].y + points[12].y) / 2)
        hip = ((points[23].x + points[24].x) / 2, (points[23].y + points[24].y) / 2)
        visible_points = [point for point in points if float(point.visibility or 0) >= 0.4]
        bbox = None
        if visible_points:
            bbox = (min(p.x for p in visible_points), min(p.y for p in visible_points), max(p.x for p in visible_points), max(p.y for p in visible_points))
        landmarks = [{
            "index": index, "x": float(point.x), "y": float(point.y), "z": float(point.z),
            "visibility": float(point.visibility or 0), "presence": float(point.presence or 0),
        } for index, point in enumerate(points)]
        missing = [item["index"] for item in landmarks if item["visibility"] < 0.4 or item["presence"] < 0.4]
        return PoseObservation(timestamp_ms / 1000, shoulder, hip, bbox, visibility, frame_id, landmarks, missing)

    def close(self):
        if self.landmarker is not None:
            self.landmarker.close()
            self.landmarker = None


pose_engine = PoseEngine()
