import json

import pytest

from app.mlops.experiment import ExperimentRecord, write_experiment_record


def record(registry="research", approved_by=None):
    return ExperimentRecord(experiment_id="detector.001", registry=registry, dataset_id="licensed-fixture-v1", dataset_source="official", dataset_license="CC-BY-4.0", manifest_version="1", model_architecture="detector", checkpoint_identity="weights-v1", checkpoint_sha256="a"*64, model_license="Apache-2.0", configuration={}, evaluation_protocol={"ground_truth":"none"}, hardware={"device":"cpu"}, runtime_versions={"python":"3.10"}, measured_results={"latency_ms":1}, git_commit="1234567", approved_by=approved_by)


def test_experiment_record_is_atomic_and_registry_separated(tmp_path):
    path = write_experiment_record(record(), tmp_path)
    assert path.parent.name == "research"
    assert json.loads(path.read_text())["dataset_license"] == "CC-BY-4.0"


def test_release_registry_requires_human_approval(tmp_path):
    with pytest.raises(ValueError): write_experiment_record(record("released"), tmp_path)
    assert write_experiment_record(record("released", "release-manager"), tmp_path).exists()
