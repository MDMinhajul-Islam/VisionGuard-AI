import json

import pytest

from app.evaluation.annotations import ValidationManifest, deterministic_annotation_id
from app.evaluation.metrics import IntervalEvent, evaluate_events, evaluate_ranked_timestamps, temporal_iou
from app.schemas.api import AnnotationCreate


def annotation(**updates):
    values = dict(video_id="v1", event_type="potential_fall", start_seconds=1, end_seconds=2, ground_truth_label="positive", annotation_source="authorized staged reviewer")
    values.update(updates)
    return AnnotationCreate(**values)


def test_annotation_id_is_deterministic_and_manifest_rejects_duplicates():
    item = annotation()
    assert deterministic_annotation_id(item) == deterministic_annotation_id(annotation())
    with pytest.raises(ValueError, match="duplicate"):
        ValidationManifest(dataset_name="d", provenance="authorized local staged data", license_or_consent="written participant consent", annotations=[item, item])


def test_annotation_interval_and_semantic_query_validation():
    with pytest.raises(ValueError):
        annotation(end_seconds=.5)
    with pytest.raises(ValueError, match="query_text"):
        annotation(event_type="semantic_search")


def test_one_to_one_event_matching_prevents_frame_level_inflation():
    truth = [IntervalEvent("g1", 10, 12, "potential_fall")]
    predictions = [IntervalEvent("p1", 10.2, 11.9, "potential_fall"), IntervalEvent("p2", 10.3, 12.1, "potential_fall")]
    result = evaluate_events(predictions, truth, .3, .5)
    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 0
    assert result["precision"] == .5


def test_timestamp_tolerance_and_false_negative_examples():
    result = evaluate_events([IntervalEvent("p", 5.8, 6.2, "potential_fall")], [IntervalEvent("g", 5, 5.3, "potential_fall")], .8, 1.0)
    assert result["true_positives"] == 1
    missed = evaluate_events([], [IntervalEvent("g", 5, 6, "potential_fall")])
    assert missed["false_negatives"] == 1
    assert missed["false_negative_examples"][0]["id"] == "g"
    empty = evaluate_events([], [])
    assert empty["precision"] is None and empty["recall"] is None and empty["f1"] is None


def test_semantic_ranking_metrics_use_timestamp_intervals():
    result = evaluate_ranked_timestamps([3.0, 7.0, 5.0], [(2.0, 4.0)], 3)
    assert result["precision_at_k"] == pytest.approx(1 / 3)
    assert result["recall_at_k"] == 1.0


def test_temporal_matching_never_crosses_record_scopes_and_keeps_negative_false_alarm():
    predictions = [
        IntervalEvent("p-fall", 1, 2, "potential_fall:fall-01"),
        IntervalEvent("p-adl", 1, 2, "potential_fall:adl-01"),
    ]
    truth = [IntervalEvent("g-fall", 1, 2, "potential_fall:fall-01")]
    result = evaluate_events(predictions, truth)
    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_positive_examples"][0]["id"] == "p-adl"
