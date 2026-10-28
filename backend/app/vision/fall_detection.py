from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field, replace
from statistics import median


@dataclass(frozen=True)
class PoseObservation:
    timestamp: float
    shoulder_center: tuple[float, float] | None
    hip_center: tuple[float, float] | None
    bbox: tuple[float, float, float, float] | None
    visibility: float
    frame_id: str = ""
    landmarks: list[dict] = field(default_factory=list)
    missing_landmarks: list[int] = field(default_factory=list)


@dataclass
class FallEvent:
    start_seconds: float
    end_seconds: float
    confidence_signal: float
    supporting_frames: list[str]
    state: str = "Potential Fall — Review Required"
    evidence: dict = field(default_factory=dict)


def pose_signals(observation: PoseObservation, confidence_threshold: float = 0.5) -> dict[str, float | bool | str | list[int]]:
    if (
        observation.visibility < confidence_threshold
        or observation.shoulder_center is None
        or observation.hip_center is None
        or observation.bbox is None
    ):
        return {
            "state": "unknown", "horizontal": False, "upright": False,
            "aspect_ratio": 0.0, "torso_angle_degrees": 0.0,
            "visibility": observation.visibility, "missing_landmarks": observation.missing_landmarks,
        }
    sx, sy = observation.shoulder_center
    hx, hy = observation.hip_center
    dx, dy = hx - sx, hy - sy
    torso_angle = math.degrees(math.atan2(abs(dx), max(abs(dy), 1e-6)))
    x1, y1, x2, y2 = observation.bbox
    aspect = max(0.0, x2 - x1) / max(y2 - y1, 1e-6)
    horizontal = torso_angle >= 55 or aspect >= 1.15
    upright = torso_angle <= 30 and aspect <= 0.85
    return {
        "state": "horizontal" if horizontal else "upright" if upright else "transitional",
        "horizontal": horizontal, "upright": upright,
        "aspect_ratio": aspect, "torso_angle_degrees": torso_angle,
        "visibility": observation.visibility, "missing_landmarks": observation.missing_landmarks,
    }


def smooth_pose_observations(observations: list[PoseObservation], window: int = 3, max_gap: float = 0.6) -> list[PoseObservation]:
    """Causal median smoothing; never interpolates across missing evidence or long gaps."""
    window = max(1, window if window % 2 else window + 1)
    history: deque[PoseObservation] = deque(maxlen=window)
    output = []
    for observation in sorted(observations, key=lambda item: item.timestamp):
        if not history or observation.timestamp - history[-1].timestamp <= max_gap:
            if observation.shoulder_center and observation.hip_center and observation.bbox:
                history.append(observation)
        else:
            history.clear()
            if observation.shoulder_center and observation.hip_center and observation.bbox:
                history.append(observation)
        if not observation.shoulder_center or not observation.hip_center or not observation.bbox or len(history) == 1:
            output.append(observation)
            continue
        output.append(replace(
            observation,
            shoulder_center=tuple(median(item.shoulder_center[i] for item in history) for i in range(2)),
            hip_center=tuple(median(item.hip_center[i] for item in history) for i in range(2)),
            bbox=tuple(median(item.bbox[i] for item in history) for i in range(4)),
            visibility=median(item.visibility for item in history),
        ))
    return output


class FallStateMachine:
    """Conservative temporal heuristic; missing evidence cannot advance a candidate."""

    def __init__(
        self, transition_window=1.5, min_vertical_drop=0.12,
        horizontal_persistence=0.6, recovery_seconds=0.5,
        confidence_threshold=0.5, max_pose_gap=0.6,
    ):
        self.transition_window = transition_window
        self.min_vertical_drop = min_vertical_drop
        self.horizontal_persistence = horizontal_persistence
        self.recovery_seconds = recovery_seconds
        self.confidence_threshold = confidence_threshold
        self.max_pose_gap = max_pose_gap
        self.history: deque[PoseObservation] = deque()
        self.reset_candidate()
        self.last_valid_timestamp: float | None = None
        self.active_event: FallEvent | None = None

    def reset_candidate(self):
        self.candidate_start: float | None = None
        self.horizontal_start: float | None = None
        self.last_horizontal: float | None = None
        self.candidate_frames: list[str] = []
        self.transition_evidence: dict = {}
        self.active_event = None

    def update(self, observation: PoseObservation) -> list[FallEvent]:
        signals = pose_signals(observation, self.confidence_threshold)
        if signals["state"] == "unknown":
            if self.last_valid_timestamp is not None and observation.timestamp - self.last_valid_timestamp > self.max_pose_gap + 1e-6:
                self.reset_candidate()
                self.history.clear()
            return []
        if self.last_valid_timestamp is not None and observation.timestamp - self.last_valid_timestamp > self.max_pose_gap + 1e-6:
            self.reset_candidate()
            self.history.clear()
        self.last_valid_timestamp = observation.timestamp
        self.history.append(observation)
        while self.history and observation.timestamp - self.history[0].timestamp > max(3.0, self.transition_window):
            self.history.popleft()

        if signals["horizontal"]:
            previous = [
                item for item in self.history
                if 0 < observation.timestamp - item.timestamp <= self.transition_window
                and pose_signals(item, self.confidence_threshold)["upright"]
            ]
            if self.candidate_start is None and previous:
                prior = previous[-1]
                vertical_drop = observation.hip_center[1] - prior.hip_center[1]  # type: ignore[index]
                if vertical_drop >= self.min_vertical_drop:
                    prior_signals = pose_signals(prior, self.confidence_threshold)
                    self.candidate_start = prior.timestamp
                    self.horizontal_start = observation.timestamp
                    self.candidate_frames = [item for item in [prior.frame_id, observation.frame_id] if item]
                    self.transition_evidence = {
                        "vertical_drop": vertical_drop,
                        "upright_torso_angle_degrees": prior_signals["torso_angle_degrees"],
                        "horizontal_torso_angle_degrees": signals["torso_angle_degrees"],
                        "upright_aspect_ratio": prior_signals["aspect_ratio"],
                        "horizontal_aspect_ratio": signals["aspect_ratio"],
                    }
            if self.candidate_start is not None:
                self.last_horizontal = observation.timestamp
                if observation.frame_id:
                    self.candidate_frames.append(observation.frame_id)
                persistence = observation.timestamp - (self.horizontal_start or observation.timestamp)
                conditions = {
                    "upright_to_horizontal": True,
                    "vertical_drop_met": self.transition_evidence.get("vertical_drop", 0) >= self.min_vertical_drop,
                    "horizontal_persistence_met": persistence + 1e-6 >= self.horizontal_persistence,
                    "pose_continuity_met": True,
                }
                if self.active_event:
                    self.active_event.end_seconds = observation.timestamp
                    self.active_event.supporting_frames = list(dict.fromkeys(self.candidate_frames))
                    self.active_event.evidence["horizontal_persistence_seconds"] = persistence
                    return []
                if all(conditions.values()):
                    self.active_event = FallEvent(
                        self.candidate_start, observation.timestamp,
                        min(1.0, 0.5 + persistence / 3),
                        list(dict.fromkeys(self.candidate_frames)),
                        evidence={
                            **self.transition_evidence,
                            "horizontal_persistence_seconds": persistence,
                            "trigger_conditions": conditions,
                            "visibility": observation.visibility,
                            "missing_landmarks": observation.missing_landmarks,
                        },
                    )
                    return [self.active_event]
        elif signals["upright"] and self.last_horizontal is not None and observation.timestamp - self.last_horizontal >= self.recovery_seconds:
            self.reset_candidate()
        return []


def detect_fall_events(observations: list[PoseObservation], smoothing_window=1, event_merge_interval=1.0, **kwargs) -> list[FallEvent]:
    max_gap = kwargs.get("max_pose_gap", 0.6)
    machine = FallStateMachine(**kwargs)
    events = []
    for observation in smooth_pose_observations(observations, smoothing_window, max_gap):
        events.extend(machine.update(observation))
    merged: list[FallEvent] = []
    for event in events:
        if merged and event.start_seconds - merged[-1].end_seconds <= event_merge_interval:
            merged[-1].end_seconds = max(merged[-1].end_seconds, event.end_seconds)
            merged[-1].supporting_frames = list(dict.fromkeys(merged[-1].supporting_frames + event.supporting_frames))
        else:
            merged.append(event)
    return merged
