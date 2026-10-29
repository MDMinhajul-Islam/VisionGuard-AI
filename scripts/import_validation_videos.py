from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

from api_auth import authenticated_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.datasets.io import write_json
from app.datasets.manifest import PreparedManifest


def wait_for_job(client: httpx.Client, job_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        response.raise_for_status()
        job = response.json()
        print(f"  {job['stage']}: {job['progress']:.0f}%", flush=True)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(2)
    raise TimeoutError(f"job {job_id} did not finish within {timeout}s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import prepared research videos through VisionGuard's supported API.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--process", action="store_true")
    parser.add_argument("--timeout", type=float, default=900)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    manifest = PreparedManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    annotations_path = args.manifest.parents[1] / "annotations" / "ur-source-temporal-labels.json"
    annotation_map: dict[str, list[dict]] = {}
    if annotations_path.exists():
        for item in json.loads(annotations_path.read_text(encoding="utf-8")).get("annotations", []):
            annotation_map.setdefault(item["record_id"], []).append(item)
    report = []
    with authenticated_client(args.api, 120) as client:
        existing = client.get("/api/datasets/assets").json()
        existing_by_key = {(item["dataset_name"], item["original_recording_id"]): item for item in existing}
        records = manifest.records[:args.limit] if args.limit else manifest.records
        for record in records:
            key = (record.source_dataset, record.original_recording_id)
            if key in existing_by_key:
                asset = existing_by_key[key]
                video_id = asset["video_id"]
                print(f"Reuse imported {record.record_id}: {video_id}")
            else:
                video_path = (PROJECT_ROOT / record.prepared_video_path).resolve()
                if not video_path.is_file():
                    report.append({"record_id": record.record_id, "status": "missing_video"})
                    continue
                with video_path.open("rb") as handle:
                    response = client.post("/api/videos/upload", files={"file": (video_path.name, handle, "video/mp4")})
                response.raise_for_status()
                video_id = response.json()["id"]
                print(f"Imported {record.record_id}: {video_id}")
            payload = {
                "video_id": video_id, "dataset_name": record.source_dataset,
                "original_recording_id": record.original_recording_id,
                "evaluation_label": record.evaluation_label, "detailed_label": record.detailed_label,
                "source_url": record.source_url, "source_license": record.source_license,
                "annotation_status": record.annotation_status, "manifest_record": record.model_dump(mode="json"),
            }
            asset_response = client.post("/api/datasets/assets", json=payload)
            asset_response.raise_for_status()
            asset = asset_response.json()
            for annotation in annotation_map.get(record.record_id, []):
                client.post("/api/validation/annotations", json={
                    "video_id": video_id, "event_type": annotation["event_type"],
                    "start_seconds": annotation["start_seconds"], "end_seconds": annotation["end_seconds"],
                    "ground_truth_label": annotation["ground_truth_label"],
                    "annotation_source": annotation["annotation_source"],
                    "reviewer_note": annotation["note"], "split": record.split,
                }).raise_for_status()
            job = None
            if args.process:
                response = client.post(f"/api/videos/{video_id}/process", json={
                    "clip_sample_seconds": 1.0, "analysis_fps": 2.0, "pose_fps": 10.0,
                    "process_width": 640, "profile_name": "real-dataset-baseline",
                })
                if response.status_code == 409 and "active" not in response.text:
                    print(f"  Processing skipped: {response.text}")
                else:
                    response.raise_for_status()
                    job = wait_for_job(client, response.json()["id"], args.timeout)
            report.append({"record_id": record.record_id, "video_id": video_id, "asset_id": asset["id"], "job": job})
    report_path = PROJECT_ROOT / "data" / "external" / "validation" / "reports" / "import-report.json"
    write_json(report_path, {"manifest": str(args.manifest), "records": report})
    print(f"Wrote {report_path}")
    return 1 if any(item.get("status") == "missing_video" or (item.get("job") or {}).get("status") == "failed" for item in report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
