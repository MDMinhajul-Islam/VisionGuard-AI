from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VideoPrediction:
    record_id: str
    ground_truth: str
    predicted_fall: bool
    event_count: int = 0


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def evaluate_video_predictions(items: list[VideoPrediction]) -> dict:
    tp = sum(item.ground_truth == "fall" and item.predicted_fall for item in items)
    fn = sum(item.ground_truth == "fall" and not item.predicted_fall for item in items)
    fp = sum(item.ground_truth == "non_fall" and item.predicted_fall for item in items)
    tn = sum(item.ground_truth == "non_fall" and not item.predicted_fall for item in items)
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
    undefined = []
    if precision is None:
        undefined.append("precision")
    if recall is None:
        undefined.append("recall")
    if f1 is None:
        undefined.append("f1")
    return {
        "videos": len(items), "true_positives": tp, "false_positives": fp,
        "true_negatives": tn, "false_negatives": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "undefined_metrics": undefined,
        "false_positive_ids": [item.record_id for item in items if item.ground_truth == "non_fall" and item.predicted_fall],
        "false_negative_ids": [item.record_id for item in items if item.ground_truth == "fall" and not item.predicted_fall],
    }
