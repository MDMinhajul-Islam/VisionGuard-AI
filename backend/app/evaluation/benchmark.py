from __future__ import annotations


def validate_benchmark_report(report: dict) -> None:
    protocol = report.get("protocol", {})
    hashes = protocol.get("source_image_sha256", [])
    if not hashes or any(len(value) != 64 for value in hashes):
        raise ValueError("benchmark must identify every source image by SHA-256")
    if protocol.get("accuracy_metrics") != "not calculated; no bounding-box ground truth":
        raise ValueError("accuracy claims require a separately validated ground-truth protocol")
    if not report.get("results"):
        raise ValueError("benchmark has no model results")
    for result in report["results"]:
        if result.get("status") == "completed":
            for group in ("inference_ms", "end_to_end_ms"):
                values = result.get(group, {})
                if any(values.get(key, -1) < 0 for key in ("mean", "p50", "p95")):
                    raise ValueError(f"invalid {group} timings")
                if values["p95"] < values["p50"]:
                    raise ValueError(f"{group} p95 cannot be lower than p50")
            if not result.get("metadata", {}).get("license"):
                raise ValueError("completed model result lacks license metadata")
