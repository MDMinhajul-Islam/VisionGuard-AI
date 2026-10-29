from app.evaluation.video_level import VideoPrediction, evaluate_video_predictions


def test_video_level_confusion_matrix_and_metrics():
    result = evaluate_video_predictions([
        VideoPrediction("fall-hit", "fall", True),
        VideoPrediction("fall-miss", "fall", False),
        VideoPrediction("adl-clear", "non_fall", False),
        VideoPrediction("adl-alarm", "non_fall", True),
    ])
    assert (result["true_positives"], result["false_negatives"]) == (1, 1)
    assert (result["true_negatives"], result["false_positives"]) == (1, 1)
    assert result["precision"] == result["recall"] == result["f1"] == 0.5
    assert result["false_positive_ids"] == ["adl-alarm"]
    assert result["false_negative_ids"] == ["fall-miss"]


def test_video_level_metrics_are_undefined_without_positive_denominators():
    result = evaluate_video_predictions([VideoPrediction("adl", "non_fall", False)])
    assert result["precision"] is None and result["recall"] is None and result["f1"] is None
