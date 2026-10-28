from __future__ import annotations

from dataclasses import dataclass, field

from app.vision.geometry import bbox_zone_overlap


@dataclass
class ObstructionSample:
    timestamp: float
    label: str
    bbox: tuple[float, float, float, float]
    confidence: float
    frame_id: str = ""
    track_id: int | None = None


@dataclass
class ObstructionEvent:
    start_seconds: float
    end_seconds: float
    labels: list[str]
    max_zone_occupancy: float
    supporting_frames: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    state: str = "Potential Exit Obstruction — Review Required"


def detect_persistent_obstructions(
    samples: list[ObstructionSample],
    polygon: list[tuple[float, float]],
    min_zone_occupancy: float = 0.15,
    min_duration: float = 2.0,
    max_gap: float = 1.0,
    event_merge_interval: float = 1.0,
) -> list[ObstructionEvent]:
    qualifying = []
    for sample in sorted(samples, key=lambda item: item.timestamp):
        overlap = bbox_zone_overlap(sample.bbox, polygon)
        if overlap >= min_zone_occupancy:
            qualifying.append((sample, overlap))
    if not qualifying:
        return []

    groups: list[list[tuple[ObstructionSample, float]]] = [[qualifying[0]]]
    for item in qualifying[1:]:
        if item[0].timestamp - groups[-1][-1][0].timestamp <= max_gap:
            groups[-1].append(item)
        else:
            groups.append([item])

    events = []
    for group in groups:
        start, end = group[0][0].timestamp, group[-1][0].timestamp
        if end - start < min_duration:
            continue
        evidence = [{
            "timestamp_seconds": sample.timestamp, "frame_id": sample.frame_id,
            "label": sample.label, "confidence": sample.confidence,
            "bbox": list(sample.bbox), "track_id": sample.track_id,
            "zone_occupancy": overlap,
        } for sample, overlap in group]
        candidate = ObstructionEvent(
            start_seconds=start, end_seconds=end,
            labels=sorted({sample.label for sample, _ in group}),
            max_zone_occupancy=max(overlap for _, overlap in group),
            supporting_frames=list(dict.fromkeys(sample.frame_id for sample, _ in group if sample.frame_id)),
            evidence=evidence,
        )
        if events and candidate.start_seconds - events[-1].end_seconds <= event_merge_interval:
            events[-1].end_seconds = candidate.end_seconds
            events[-1].labels = sorted(set(events[-1].labels + candidate.labels))
            events[-1].max_zone_occupancy = max(events[-1].max_zone_occupancy, candidate.max_zone_occupancy)
            events[-1].supporting_frames = list(dict.fromkeys(events[-1].supporting_frames + candidate.supporting_frames))
            events[-1].evidence.extend(candidate.evidence)
        else:
            events.append(candidate)
    return events
