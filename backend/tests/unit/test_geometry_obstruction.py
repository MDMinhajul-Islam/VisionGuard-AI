import pytest

from app.vision.geometry import bbox_zone_overlap, polygon_area
from app.vision.obstruction_detection import ObstructionSample, detect_persistent_obstructions


ZONE = [(0.5, 0.5), (0.9, 0.5), (0.9, 0.9), (0.5, 0.9)]


def sample(timestamp, bbox, label="chair"):
    return ObstructionSample(timestamp, label, bbox, 0.9, f"f-{timestamp}", 7)


def test_polygon_and_overlap_cases():
    assert polygon_area(ZONE) == pytest.approx(0.16)
    assert bbox_zone_overlap((0.0, 0.0, 0.2, 0.2), ZONE) == 0
    assert bbox_zone_overlap((0.5, 0.5, 0.9, 0.9), ZONE) == pytest.approx(1.0)
    assert 0 < bbox_zone_overlap((0.4, 0.4, 0.6, 0.6), ZONE) < 1
    with pytest.raises(ValueError):
        bbox_zone_overlap((0, 0, 1, 1), [(0, 0), (1, 1), (2, 2)])


@pytest.mark.parametrize(
    "samples,expected",
    [
        ([], 0),
        ([sample(0, (0, 0, .2, .2))], 0),
        ([sample(0, (.55, .55, .8, .8)), sample(.5, (.55, .55, .8, .8))], 0),
        ([sample(0, (.55, .55, .8, .8)), sample(1, (.55, .55, .8, .8)), sample(2, (.55, .55, .8, .8))], 1),
        ([sample(0, (.55, .55, .8, .8)), sample(.8, (.55, .55, .8, .8)), sample(1.6, (0, 0, .2, .2)), sample(2.4, (.55, .55, .8, .8))], 0),
        ([sample(0, (.55, .55, .8, .8), "chair"), sample(1, (.55, .55, .8, .8), "suitcase"), sample(2, (.55, .55, .8, .8), "chair")], 1),
    ],
)
def test_temporal_obstruction_cases(samples, expected):
    events = detect_persistent_obstructions(samples, ZONE)
    assert len(events) == expected
    if events:
        assert events[0].end_seconds - events[0].start_seconds >= 2
        assert events[0].evidence[0]["track_id"] == 7
        assert events[0].evidence[0]["zone_occupancy"] >= .15

