from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate actual VisionGuard fall candidates against dataset labels.")
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", default="UR Fall Detection")
    parser.add_argument("--diagnostics", action="store_true")
    args = parser.parse_args()
    report_root = PROJECT_ROOT / "data" / "external" / "validation" / "reports"
    report_root.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=args.api, timeout=120) as client:
        response = client.get("/api/datasets/evaluation", params={"dataset_name": args.dataset, "completed_only": "true"})
        response.raise_for_status()
        report = response.json()
        report["generated_at"] = datetime.now(timezone.utc).isoformat()
        assets = client.get("/api/datasets/assets", params={"dataset_name": args.dataset}).json()
        temporal_results = []
        for item in assets:
            if item["evaluation_label"] == "fall" and item["annotation_status"] != "source_frame_labels":
                continue
            temporal = client.post(f"/api/videos/{item['video_id']}/evaluate", json={
                "event_type": "potential_fall", "split": "evaluation",
                "temporal_iou_threshold": 0.3, "onset_tolerance_seconds": 1.0,
            })
            temporal.raise_for_status()
            temporal_results.append({"record_id": item["original_recording_id"], **temporal.json()})
        event_tp = sum(item["true_positives"] for item in temporal_results)
        event_fp = sum(item["false_positives"] for item in temporal_results)
        event_fn = sum(item["false_negatives"] for item in temporal_results)
        event_precision = event_tp / (event_tp + event_fp) if event_tp + event_fp else None
        event_recall = event_tp / (event_tp + event_fn) if event_tp + event_fn else None
        event_f1 = 2 * event_precision * event_recall / (event_precision + event_recall) if event_precision is not None and event_recall is not None and event_precision + event_recall else None
        matches = [match for item in temporal_results for match in item["matches"]]
        report["temporal_evaluation"] = {
            "scope": "All predictions from ten annotated falls and ten video-level non-fall negative controls. Positive intervals use UR cam0 depth posture label 0 mapped to RGB synchronization timestamps.",
            "videos_with_source_intervals": len(temporal_results),
            "true_positives": event_tp, "false_positives": event_fp, "false_negatives": event_fn,
            "precision": event_precision, "recall": event_recall, "f1": event_f1,
            "mean_detection_delay_seconds": sum(item["detection_delay_seconds"] for item in matches) / len(matches) if matches else None,
            "mean_timestamp_localization_error_seconds": sum(item["timestamp_localization_error_seconds"] for item in matches) / len(matches) if matches else None,
            "matching": "greedy one-to-one; temporal IoU >= 0.3 OR onset error <= 1.0 second",
            "limitation": "Positive transition labels originate from synchronized depth-frame posture features, not independent RGB human event-onset annotation. Non-fall videos provide video-level negative controls but no temporal intervals.",
            "per_video": temporal_results,
        }
        metric_rows = [row["processing_metrics"] for row in report["records"]]
        pose_frames = sum(row.get("pose_frames", 0) for row in metric_rows)
        report["performance"] = {
            "source_video_duration_seconds": sum(row.get("duration_seconds") or 0 for row in report["records"]),
            "total_processing_seconds": sum(row.get("total_processing_seconds", 0) for row in metric_rows),
            "frames_extracted": sum(row.get("frames_extracted", 0) for row in metric_rows),
            "pose_frames": pose_frames,
            "pose_frames_with_sufficient_evidence": sum(row.get("pose_frames_with_sufficient_evidence", 0) for row in metric_rows),
            "weighted_average_pose_inference_ms": sum(row.get("average_pose_inference_ms", 0) * row.get("pose_frames", 0) for row in metric_rows) / pose_frames if pose_frames else None,
            "clip_indexing_seconds": sum(row.get("clip_indexing_seconds", 0) for row in metric_rows),
            "detection_seconds": sum(row.get("detection_seconds", 0) for row in metric_rows),
            "peak_gpu_memory_mib": max((row.get("peak_gpu_memory_mib", 0) for row in metric_rows), default=0),
        }
        system = client.get("/api/system/info")
        if system.is_success:
            report["system"] = system.json()
        if args.diagnostics:
            diagnostic_root = report_root / "diagnostics"
            target_ids = set(report["metrics"]["false_positive_ids"] + report["metrics"]["false_negative_ids"])
            for row in report["records"]:
                if row["record_id"] not in target_ids:
                    continue
                if row["record_id"] in report["metrics"]["false_positive_ids"]:
                    target_time = row["candidate_timestamps"][0] if row["candidate_timestamps"] else (row["duration_seconds"] or 0) / 2
                    reason = "false_positive_first_candidate"
                else:
                    annotations = client.get("/api/validation/annotations", params={"video_id": row["video_id"]}).json()
                    positive = next((item for item in annotations if item["event_type"] == "potential_fall" and item["ground_truth_label"] == "positive"), None)
                    target_time = (positive["start_seconds"] + positive["end_seconds"]) / 2 if positive else (row["duration_seconds"] or 0) / 2
                    reason = "false_negative_source_interval_midpoint" if positive else "false_negative_video_midpoint_no_temporal_annotation"
                frames_response = client.get(f"/api/videos/{row['video_id']}/frames")
                frames_response.raise_for_status()
                frames = frames_response.json()
                if not frames:
                    continue
                frame = min(frames, key=lambda item: abs(item["timestamp_seconds"] - target_time))
                output = diagnostic_root / row["record_id"]
                output.mkdir(parents=True, exist_ok=True)
                for kind, url in (("original", frame["image_url"]), ("overlay", frame["overlay_url"])):
                    image = client.get(url)
                    image.raise_for_status()
                    (output / f"{kind}.jpg").write_bytes(image.content)
                evidence = client.get(f"/api/frames/{frame['id']}/evidence")
                evidence.raise_for_status()
                (output / "evidence.json").write_text(json.dumps({
                    "record_id": row["record_id"], "ground_truth": row["ground_truth"],
                    "predicted_fall": row["predicted_fall"], "diagnostic_reason": reason,
                    "target_seconds": target_time, "selected_frame_seconds": frame["timestamp_seconds"],
                    "frame_evidence": evidence.json(),
                }, indent=2), encoding="utf-8")
    destination = report_root / "real-fall-evaluation.json"
    destination.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Wrote {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
