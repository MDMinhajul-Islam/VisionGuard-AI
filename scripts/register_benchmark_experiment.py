from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.mlops.experiment import ExperimentRecord, write_experiment_record


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.casefold()).strip("-")


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a validated detector benchmark as research experiments.")
    parser.add_argument("report", type=Path)
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "evaluations" / "registry")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    written = []
    for result in report["results"]:
        if result.get("status") != "completed":
            continue
        metadata = result["metadata"]
        record = ExperimentRecord(
            experiment_id=f"sprint3-{slug(metadata['model_id'])}",
            registry="research",
            dataset_id="ur-fall-local-frame-sample-sprint3",
            dataset_source="University of Rzeszow UR Fall Detection Dataset",
            dataset_license="CC BY-NC-SA 4.0; non-commercial academic use",
            manifest_version="five-frame-sha256-set-v1",
            model_architecture=metadata["architecture"],
            checkpoint_identity=metadata["checkpoint"],
            checkpoint_sha256=result.get("checkpoint_sha256"),
            model_license=metadata["license"],
            configuration={"threshold": report["protocol"]["threshold"], "input_canvas": report["protocol"]["input_canvas"]},
            evaluation_protocol=report["protocol"], hardware=report["hardware"],
            runtime_versions={"python": report["hardware"]["python"], "torch": report["hardware"]["torch"], "cuda": report["hardware"]["cuda"]},
            measured_results={key: value for key, value in result.items() if key not in {"metadata", "status"}},
            git_commit=report["git_commit"],
        )
        written.append(str(write_experiment_record(record, args.output_root)))
    print(json.dumps({"records": written}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
