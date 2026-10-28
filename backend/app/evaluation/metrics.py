from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class IntervalEvent:
    id: str
    start_seconds: float
    end_seconds: float
    event_type: str


def temporal_iou(left: IntervalEvent, right: IntervalEvent) -> float:
    intersection = max(0.0, min(left.end_seconds, right.end_seconds) - max(left.start_seconds, right.start_seconds))
    union = max(left.end_seconds, right.end_seconds) - min(left.start_seconds, right.start_seconds)
    return intersection / union if union > 0 else 0.0


def evaluate_events(
    predictions: list[IntervalEvent],
    ground_truth: list[IntervalEvent],
    iou_threshold: float = 0.3,
    onset_tolerance_seconds: float = 1.0,
) -> dict:
    """Greedy one-to-one event matching; adjacent frames never count as separate hits."""
    candidates = []
    for prediction in predictions:
        for truth in ground_truth:
            if prediction.event_type != truth.event_type:
                continue
            overlap = temporal_iou(prediction, truth)
            onset_error = abs(prediction.start_seconds - truth.start_seconds)
            if overlap >= iou_threshold or onset_error <= onset_tolerance_seconds:
                candidates.append((overlap, -onset_error, prediction, truth))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    used_predictions: set[str] = set()
    used_truth: set[str] = set()
    matches = []
    for overlap, _, prediction, truth in candidates:
        if prediction.id in used_predictions or truth.id in used_truth:
            continue
        used_predictions.add(prediction.id)
        used_truth.add(truth.id)
        matches.append({
            "prediction_id": prediction.id,
            "ground_truth_id": truth.id,
            "temporal_iou": overlap,
            "detection_delay_seconds": prediction.start_seconds - truth.start_seconds,
            "timestamp_localization_error_seconds": abs(prediction.start_seconds - truth.start_seconds),
        })
    false_positives = [asdict(item) for item in predictions if item.id not in used_predictions]
    false_negatives = [asdict(item) for item in ground_truth if item.id not in used_truth]
    true_positives = len(matches)
    fp, fn = len(false_positives), len(false_negatives)
    precision = true_positives / (true_positives + fp) if true_positives + fp else None
    recall = true_positives / (true_positives + fn) if true_positives + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {
        "true_positives": true_positives, "false_positives": fp, "false_negatives": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "mean_detection_delay_seconds": sum(item["detection_delay_seconds"] for item in matches) / len(matches) if matches else None,
        "mean_timestamp_localization_error_seconds": sum(item["timestamp_localization_error_seconds"] for item in matches) / len(matches) if matches else None,
        "matches": matches, "false_positive_examples": false_positives, "false_negative_examples": false_negatives,
        "protocol": {"matching": "greedy one-to-one", "temporal_iou_threshold": iou_threshold, "onset_tolerance_seconds": onset_tolerance_seconds},
        "undefined_metrics": [name for name, value in (("precision", precision), ("recall", recall), ("f1", f1)) if value is None],
    }


def evaluate_ranked_timestamps(results: list[float], relevant_intervals: list[tuple[float, float]], k: int) -> dict:
    ranked = results[:k]
    hits = [any(start <= timestamp <= end for start, end in relevant_intervals) for timestamp in ranked]
    retrieved_intervals = {
        index for index, (start, end) in enumerate(relevant_intervals)
        if any(start <= timestamp <= end for timestamp in ranked)
    }
    errors = [min(abs(timestamp - start), abs(timestamp - end), 0.0 if start <= timestamp <= end else float("inf")) for timestamp in ranked for start, end in relevant_intervals]
    return {
        "precision_at_k": sum(hits) / len(ranked) if ranked else 0.0,
        "recall_at_k": len(retrieved_intervals) / len(relevant_intervals) if relevant_intervals else 0.0,
        "timestamp_hit_count": sum(hits), "k": k,
        "minimum_timestamp_localization_error_seconds": min(errors) if errors else None,
    }
