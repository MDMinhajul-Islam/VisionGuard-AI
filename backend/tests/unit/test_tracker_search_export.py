from pathlib import Path

import numpy as np
import pytest

from app.services.exporter import validate_clip_range
from app.services.video_io import parse_rate, safe_within
from app.vision.clip_engine import CLIPEngine
from app.vision.tracker import IoUTracker, iou


def test_timestamp_rate_and_safe_paths(tmp_path):
    assert parse_rate("30000/1001") == pytest.approx(29.970, rel=1e-3)
    assert parse_rate("0/0") == 0
    assert safe_within(tmp_path / "file.mp4", tmp_path) == (tmp_path / "file.mp4").resolve()
    with pytest.raises(ValueError):
        safe_within(tmp_path.parent / "escape.mp4", tmp_path)


def test_clip_range_validation():
    validate_clip_range(1, 2, 3)
    for start, end, duration in [(-1, 2, 3), (2, 1, 3), (0, 4, 3), (0, 301, 400)]:
        with pytest.raises(ValueError):
            validate_clip_range(start, end, duration)


def test_iou_tracker_associates_and_expires():
    tracker = IoUTracker(iou_threshold=.2, max_missed_frames=1)
    first = tracker.update([{"label": "person", "confidence": .9, "bbox": (0, 0, 1, 1)}], 0)
    second = tracker.update([{"label": "person", "confidence": .8, "bbox": (.05, 0, 1, 1)}], 1)
    assert first[0]["track_id"] == second[0]["track_id"]
    tracker.update([], 3)
    assert tracker.tracks == {}
    assert iou((0, 0, 1, 1), (2, 2, 3, 3)) == 0


def test_semantic_ranking_temporal_suppression(tmp_path, monkeypatch):
    cache = tmp_path / "index.npz"
    np.savez(cache, features=np.asarray([[1, 0], [.99, .01], [0, 1]], np.float32), timestamps=np.asarray([0, 1, 5]), frame_ids=np.asarray(["a", "b", "c"]))
    engine = CLIPEngine()
    monkeypatch.setattr(engine, "encode_text", lambda _: np.asarray([1, 0], np.float32))
    results = engine.search(cache, "query", 3, suppression_seconds=2)
    assert [item["frame_id"] for item in results] == ["a", "c"]

