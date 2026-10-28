from __future__ import annotations

from dataclasses import dataclass, field


def iou(a, b) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1]) + max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1]) - intersection
    return intersection / union if union else 0.0


@dataclass
class Track:
    id: int
    label: str
    bbox: tuple[float, float, float, float]
    last_frame: int
    history: list[tuple[int, tuple[float, float, float, float]]] = field(default_factory=list)


class IoUTracker:
    """Per-video short-term tracker; no identity or cross-video re-identification."""

    def __init__(self, iou_threshold: float = 0.3, max_missed_frames: int = 4):
        self.iou_threshold = iou_threshold
        self.max_missed_frames = max_missed_frames
        self.tracks: dict[int, Track] = {}
        self.next_id = 1

    def update(self, detections: list[dict], frame_number: int) -> list[dict]:
        candidates = set(self.tracks)
        for detection in sorted(detections, key=lambda item: item["confidence"], reverse=True):
            best_id, best_iou = None, 0.0
            for track_id in candidates:
                track = self.tracks[track_id]
                if track.label != detection["label"]:
                    continue
                score = iou(track.bbox, detection["bbox"])
                if score > best_iou:
                    best_id, best_iou = track_id, score
            if best_id is None or best_iou < self.iou_threshold:
                best_id = self.next_id
                self.next_id += 1
                self.tracks[best_id] = Track(best_id, detection["label"], detection["bbox"], frame_number)
            track = self.tracks[best_id]
            track.bbox = detection["bbox"]
            track.last_frame = frame_number
            track.history.append((frame_number, detection["bbox"]))
            track.history = track.history[-30:]
            candidates.discard(best_id)
            detection["track_id"] = best_id
        stale = [track_id for track_id, track in self.tracks.items() if frame_number - track.last_frame > self.max_missed_frames]
        for track_id in stale:
            del self.tracks[track_id]
        return detections

