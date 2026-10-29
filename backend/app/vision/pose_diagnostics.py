from __future__ import annotations

from dataclasses import asdict

from app.vision.fall_detection import PoseObservation, detect_fall_events, pose_signals


BASELINE_PROFILE = {
    "name": "real-dataset-baseline",
    "transition_window": 1.5,
    "min_vertical_drop": 0.12,
    "horizontal_persistence": 0.6,
    "confidence_threshold": 0.5,
    "max_pose_gap": 0.6,
    "smoothing_window": 3,
    "event_merge_interval": 1.0,
    "min_horizontal_aspect": 0.0,
}

IMPROVED_PROFILE = {
    **BASELINE_PROFILE,
    "name": "diagnostic-shape-gated-v1",
    "horizontal_persistence": 0.08,
    "min_horizontal_aspect": 0.8,
}


def observation_from_landmarks(timestamp: float, frame_id: str, landmarks: list[dict]) -> PoseObservation:
    if not landmarks:
        return PoseObservation(timestamp, None, None, None, 0.0, frame_id, [], list(range(33)))
    points = {int(item["index"]): item for item in landmarks}
    required = [11, 12, 23, 24, 27, 28]
    if any(index not in points for index in required):
        return PoseObservation(timestamp, None, None, None, 0.0, frame_id, landmarks, required)
    visibility = sum(float(points[index].get("visibility", 0)) for index in required) / len(required)
    shoulder = (
        (float(points[11]["x"]) + float(points[12]["x"])) / 2,
        (float(points[11]["y"]) + float(points[12]["y"])) / 2,
    )
    hip = (
        (float(points[23]["x"]) + float(points[24]["x"])) / 2,
        (float(points[23]["y"]) + float(points[24]["y"])) / 2,
    )
    visible = [item for item in landmarks if float(item.get("visibility", 0)) >= 0.4]
    bbox = None if not visible else (
        min(float(item["x"]) for item in visible), min(float(item["y"]) for item in visible),
        max(float(item["x"]) for item in visible), max(float(item["y"]) for item in visible),
    )
    missing = [
        int(item["index"]) for item in landmarks
        if float(item.get("visibility", 0)) < 0.4 or float(item.get("presence", 0)) < 0.4
    ]
    return PoseObservation(timestamp, shoulder, hip, bbox, visibility, frame_id, landmarks, missing)


def diagnostic_series(observations: list[PoseObservation], profile: dict = BASELINE_PROFILE) -> list[dict]:
    output = []
    valid_history: list[PoseObservation] = []
    for observation in sorted(observations, key=lambda item: item.timestamp):
        signals = pose_signals(observation, profile["confidence_threshold"])
        if signals["state"] != "unknown":
            valid_history.append(observation)
        prior = [
            item for item in valid_history[:-1]
            if 0 < observation.timestamp - item.timestamp <= profile["transition_window"]
            and pose_signals(item, profile["confidence_threshold"])["upright"]
        ]
        vertical_drop = None
        if prior and observation.hip_center:
            vertical_drop = observation.hip_center[1] - prior[-1].hip_center[1]  # type: ignore[index]
        output.append({
            "timestamp_seconds": observation.timestamp,
            "state": signals["state"],
            "torso_angle_degrees": signals["torso_angle_degrees"],
            "aspect_ratio": signals["aspect_ratio"],
            "hip_y": observation.hip_center[1] if observation.hip_center else None,
            "bbox_center_y": (observation.bbox[1] + observation.bbox[3]) / 2 if observation.bbox else None,
            "bbox_width": observation.bbox[2] - observation.bbox[0] if observation.bbox else None,
            "bbox_height": observation.bbox[3] - observation.bbox[1] if observation.bbox else None,
            "vertical_drop_from_recent_upright": vertical_drop,
            "visibility": observation.visibility,
            "missing_landmarks": observation.missing_landmarks,
            "missing_lower_body": [index for index in observation.missing_landmarks if 23 <= index <= 32],
            "frame_id": observation.frame_id,
        })
    return output


def run_profile(observations: list[PoseObservation], profile: dict) -> list[dict]:
    arguments = {key: value for key, value in profile.items() if key != "name"}
    return [asdict(event) for event in detect_fall_events(observations, **arguments)]


def summarize_diagnostics(series: list[dict]) -> dict:
    valid = [item for item in series if item["state"] != "unknown"]
    gaps = [right["timestamp_seconds"] - left["timestamp_seconds"] for left, right in zip(valid, valid[1:])]
    drops = [item["vertical_drop_from_recent_upright"] for item in series if item["vertical_drop_from_recent_upright"] is not None]
    return {
        "pose_samples": len(series),
        "valid_pose_samples": len(valid),
        "unknown_pose_samples": len(series) - len(valid),
        "pose_availability": len(valid) / len(series) if series else 0.0,
        "max_valid_gap_seconds": max(gaps, default=0.0),
        "max_torso_angle_degrees": max((item["torso_angle_degrees"] for item in series), default=0.0),
        "max_aspect_ratio": max((item["aspect_ratio"] for item in series), default=0.0),
        "max_vertical_drop_from_recent_upright": max(drops, default=None),
        "state_counts": {state: sum(item["state"] == state for item in series) for state in ("upright", "transitional", "horizontal", "unknown")},
    }
