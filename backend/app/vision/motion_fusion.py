from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.vision.fall_detection import FallEvent, PoseObservation, pose_signals


MOTION_FUSION_PROFILE = {
    "name": "bbox-motion-fusion-v1", "transition_window": 1.5,
    "min_center_drop": 0.10, "min_aspect_change": 0.25,
    "min_end_aspect": 0.8, "confidence_threshold": 0.5,
}


@dataclass(frozen=True)
class BoxMotion:
    start_seconds: float
    end_seconds: float
    center_drop: float
    aspect_change: float
    end_aspect: float
    track_continuous: bool


def box_motion(prior: PoseObservation, current: PoseObservation, max_gap: float = 1.5) -> BoxMotion | None:
    if not prior.bbox or not current.bbox or not 0 < current.timestamp - prior.timestamp <= max_gap:
        return None
    px1, py1, px2, py2 = prior.bbox
    cx1, cy1, cx2, cy2 = current.bbox
    prior_center_y = (py1 + py2) / 2
    current_center_y = (cy1 + cy2) / 2
    prior_aspect = (px2 - px1) / max(py2 - py1, 1e-6)
    current_aspect = (cx2 - cx1) / max(cy2 - cy1, 1e-6)
    return BoxMotion(prior.timestamp, current.timestamp, current_center_y - prior_center_y, current_aspect - prior_aspect, current_aspect, True)


def camera_compensated_flow(previous_gray: np.ndarray, current_gray: np.ndarray, subject_bbox: tuple[int, int, int, int]) -> dict:
    """Farneback flow with median background translation removed; returns measured pixel motion."""
    flow = cv2.calcOpticalFlowFarneback(previous_gray, current_gray, None, .5, 3, 15, 3, 5, 1.2, 0)
    x1, y1, x2, y2 = subject_bbox
    mask = np.ones(previous_gray.shape, dtype=bool)
    mask[max(0, y1):min(mask.shape[0], y2), max(0, x1):min(mask.shape[1], x2)] = False
    background = flow[mask]
    camera = np.median(background, axis=0) if background.size else np.zeros(2, dtype=np.float32)
    subject = flow[max(0, y1):min(flow.shape[0], y2), max(0, x1):min(flow.shape[1], x2)] - camera
    return {
        "camera_dx": float(camera[0]), "camera_dy": float(camera[1]),
        "subject_dx": float(np.median(subject[..., 0])) if subject.size else 0.0,
        "subject_dy": float(np.median(subject[..., 1])) if subject.size else 0.0,
        "subject_motion_magnitude": float(np.median(np.linalg.norm(subject, axis=2))) if subject.size else 0.0,
    }


def detect_motion_fusion_events(
    observations: list[PoseObservation], *, transition_window: float = 1.5,
    min_center_drop: float = 0.10, min_aspect_change: float = 0.25,
    min_end_aspect: float = 0.8, confidence_threshold: float = 0.5,
) -> list[FallEvent]:
    """Experimental pose/box fusion. It never fabricates missing boxes or confirms incidents."""
    ordered = sorted(observations, key=lambda item: item.timestamp)
    events: list[FallEvent] = []
    for index, current in enumerate(ordered):
        current_signals = pose_signals(current, confidence_threshold)
        candidates = [
            prior for prior in ordered[:index]
            if 0 < current.timestamp - prior.timestamp <= transition_window
            and pose_signals(prior, confidence_threshold)["upright"]
        ]
        if not candidates:
            continue
        prior = candidates[-1]
        motion = box_motion(prior, current, transition_window)
        if not motion:
            continue
        shape_change = motion.aspect_change >= min_aspect_change or bool(current_signals["horizontal"])
        conditions = {
            "recent_upright_pose": True,
            "bbox_center_drop_met": motion.center_drop >= min_center_drop,
            "bbox_aspect_change_or_horizontal_pose": shape_change,
            "bbox_end_aspect_met": motion.end_aspect >= min_end_aspect,
        }
        if all(conditions.values()):
            events.append(FallEvent(
                prior.timestamp, current.timestamp, 1.0,
                [item for item in (prior.frame_id, current.frame_id) if item],
                evidence={
                    "fusion_method": "pose_plus_landmark_bbox_motion",
                    "bbox_center_drop": motion.center_drop,
                    "bbox_aspect_change": motion.aspect_change,
                    "bbox_end_aspect": motion.end_aspect,
                    "pose_state": current_signals["state"],
                    "trigger_conditions": conditions,
                    "missing_landmarks": current.missing_landmarks,
                },
            ))
            break
    return events
