from pathlib import Path

import pytest

from scripts.prepare_research_videos import read_sync, source_intervals


def test_sync_loader_preserves_source_milliseconds(tmp_path: Path):
    path = tmp_path / "sync.csv"
    path.write_text("1,0,1.0\n2,33,1.1\n3,67,1.0\n", encoding="utf-8")
    assert read_sync(path) == {1: 0.0, 2: 0.033, 3: 0.067}


def test_sync_loader_rejects_non_monotonic_timing(tmp_path: Path):
    path = tmp_path / "sync.csv"
    path.write_text("1,0,1.0\n2,0,1.1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="strictly increasing"):
        read_sync(path)


def test_sync_loader_rejects_missing_timing_instead_of_inventing_frame_rate(tmp_path: Path):
    path = tmp_path / "sync.csv"
    path.write_text("frame,timestamp,acceleration\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no synchronization timestamps"):
        read_sync(path)


def test_source_transition_interval_uses_only_verified_zero_labels():
    timestamps = {1: 0.0, 2: 0.033, 3: 0.067, 4: 0.1}
    labels = {"fall-01": {1: -1, 2: 0, 3: 0, 4: 1}}
    result = source_intervals("fall-01", timestamps, labels)
    assert result[0]["start_seconds"] == 0.033
    assert result[0]["end_seconds"] == pytest.approx(0.1)
    assert source_intervals("adl-01", timestamps, labels) == []


def test_adl_zero_posture_is_not_promoted_to_fall_ground_truth():
    timestamps = {1: 0.0, 2: 0.033, 3: 0.067}
    labels = {"adl-01": {1: -1, 2: 0, 3: 1}}
    assert source_intervals("adl-01", timestamps, labels) == []
