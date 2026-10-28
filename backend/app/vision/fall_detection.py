from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class PoseObservation:
    timestamp: float
    shoulder_center: tuple[float, float] | None
    hip_center: tuple[float, float] | None
    bbox: tuple[float, float, float, float] | None
    visibility: float
    frame_id: str = ""


@dataclass
class FallEvent:
    start_seconds: float
    end_seconds: float
    confidence_signal: float
    supporting_frames: list[str]
    state: str = "Potential Fall — Review Required"


def pose_signals(observation: PoseObservation) -> dict[str, float | bool | str]:
    if (
        observation.visibility < 0.5
        or observation.shoulder_center is None
        or observation.hip_center is None
        or observation.bbox is None
    ):
        return {"state": "unknown", "horizontal": False, "upright": False, "aspect_ratio": 0.0, "torso_angle": 0.0}
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
        "horizontal": horizontal,
        "upright": upright,
        "aspect_ratio": aspect,
        "torso_angle": torso_angle,
    }


class FallStateMachine:
    """Conservative temporal heuristic; outputs candidates, never confirmed falls."""

    def __init__(self, transition_window=1.5, min_vertical_drop=0.12, horizontal_persistence=0.6, recovery_seconds=0.5):
        self.transition_window = transition_window
        self.min_vertical_drop = min_vertical_drop
        self.horizontal_persistence = horizontal_persistence
        self.recovery_seconds = recovery_seconds
        self.history: deque[PoseObservation] = deque()
        self.candidate_start: float | None = None
        self.candidate_frames: list[str] = []
        self.last_horizontal: float | None = None
        self.emitted_for_candidate = False

    def update(self, observation: PoseObservation) -> list[FallEvent]:
        self.history.append(observation)
        while self.history and observation.timestamp - self.history[0].timestamp > 3.0:
            self.history.popleft()
        signals = pose_signals(observation)
        if signals["state"] == "unknown":
            return []

        if signals["horizontal"]:
            previous = [item for item in self.history if 0 < observation.timestamp - item.timestamp <= self.transition_window and pose_signals(item)["upright"]]
            if self.candidate_start is None and previous:
                prior = previous[-1]
                vertical_drop = observation.hip_center[1] - prior.hip_center[1]  # type: ignore[index]
                if vertical_drop >= self.min_vertical_drop:
                    self.candidate_start = prior.timestamp
                    self.candidate_frames = [prior.frame_id] if prior.frame_id else []
                    self.emitted_for_candidate = False
            if self.candidate_start is not None:
                self.last_horizontal = observation.timestamp
                if observation.frame_id:
                    self.candidate_frames.append(observation.frame_id)
                if not self.emitted_for_candidate and observation.timestamp - self.candidate_start >= self.horizontal_persistence:
                    self.emitted_for_candidate = True
                    return [FallEvent(
                        self.candidate_start,
                        observation.timestamp,
                        min(1.0, 0.5 + (observation.timestamp - self.candidate_start) / 3),
                        list(dict.fromkeys(self.candidate_frames)),
                    )]
        elif signals["upright"] and self.last_horizontal is not None and observation.timestamp - self.last_horizontal >= self.recovery_seconds:
            self.candidate_start = None
            self.candidate_frames = []
            self.last_horizontal = None
            self.emitted_for_candidate = False
        return []


def detect_fall_events(observations: list[PoseObservation], **kwargs) -> list[FallEvent]:
    machine = FallStateMachine(**kwargs)
    events = []
    for observation in sorted(observations, key=lambda item: item.timestamp):
        events.extend(machine.update(observation))
    return events

