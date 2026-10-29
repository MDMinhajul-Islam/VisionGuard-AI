import pytest

from app.evaluation.benchmark import validate_benchmark_report
from app.vision.detectors.base import DetectorMetadata, validate_detections


def detection(**updates):
    row = {"label": "person", "confidence": .8, "bbox": (.1, .2, .5, .9), "bbox_pixels": (10, 20, 50, 90), "model_id": "test", "model_version": "1", "device": "cpu", "provenance": "unit:test"}
    row.update(updates)
    return row


def test_normalized_detector_contract_and_metadata():
    validate_detections([detection()])
    metadata = DetectorMetadata("test", "1", "fixture", "fixture.bin", "Apache-2.0", True, "cpu", ("person",))
    assert metadata.to_dict()["commercial_runtime_eligible"] is True
    with pytest.raises(ValueError): validate_detections([detection(bbox=(-.1, 0, .5, .5))])
    with pytest.raises(ValueError): validate_detections([detection(confidence=1.1)])


def test_benchmark_report_requires_provenance_timings_and_no_fake_accuracy():
    report = {"protocol": {"source_image_sha256": ["a" * 64], "accuracy_metrics": "not calculated; no bounding-box ground truth"}, "results": [{"status": "completed", "metadata": {"license": "Apache-2.0"}, "inference_ms": {"mean": 2, "p50": 1, "p95": 3}, "end_to_end_ms": {"mean": 3, "p50": 2, "p95": 4}}]}
    validate_benchmark_report(report)
    report["protocol"]["accuracy_metrics"] = "mAP 99"
    with pytest.raises(ValueError): validate_benchmark_report(report)
