from __future__ import annotations

import argparse
import json
import sys
import time
import math
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.database.models import DatasetAsset, PoseEvidence, ValidationAnnotation
from app.database.session import SessionLocal
from app.evaluation.metrics import IntervalEvent, evaluate_events
from app.evaluation.video_level import VideoPrediction, evaluate_video_predictions
from app.vision.pose_diagnostics import (
    BASELINE_PROFILE, IMPROVED_PROFILE, diagnostic_series, observation_from_landmarks,
    run_profile, summarize_diagnostics,
)
from app.vision.motion_fusion import MOTION_FUSION_PROFILE, detect_motion_fusion_events


CALIBRATION_IDS = {"fall-02", "fall-18", "fall-19", "fall-20", "adl-01", "adl-03", "adl-30", "adl-32"}
ORIGINAL_20_IDS = {
    "fall-02", "fall-07", "fall-18", "fall-19", "fall-20", "fall-22", "fall-23", "fall-24", "fall-25", "fall-26",
    "adl-01", "adl-03", "adl-10", "adl-14", "adl-15", "adl-17", "adl-19", "adl-30", "adl-32", "adl-35",
}
ROOT_CAUSES = {
    "fall-18": "A strong horizontal transition and vertical drop are present, but the visible horizontal run is shorter than the baseline 0.6 s persistence threshold.",
    "fall-19": "MediaPipe never reports a horizontal sample; torso angle and vertical drop remain below baseline transition thresholds and pose availability is interrupted.",
    "fall-20": "Horizontal samples occur without a qualifying recent upright-to-horizontal hip drop; the measured drop stays below 0.12 within the transition window.",
    "fall-23": "The pose remains classified upright throughout valid samples. A late hip displacement exists, but the torso-orientation condition is absent.",
    "fall-25": "Only one horizontal sample is available and its drop is below 0.12, so neither drop nor persistence reaches baseline requirements.",
    "fall-26": "Horizontal evidence is brief, the measured hip drop is below 0.12, and 8 of 21 samples are unknown, preventing a qualifying continuous transition.",
    "adl-30": "Torso rotation alone crosses 55 degrees while the trigger-frame full-body aspect is 0.56 and lower-leg landmarks are missing; the baseline lacks a body-shape gate.",
}


def wilson_interval(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    if total <= 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def load_observations(rows):
    return [
        observation_from_landmarks(row.timestamp_seconds, row.frame_id, json.loads(row.landmarks_json))
        for row in rows
    ]


def evaluate_profile(records: list[dict], profile: dict, runner=run_profile) -> dict:
    started = time.perf_counter()
    rows = []
    temporal_predictions: list[IntervalEvent] = []
    temporal_truth: list[IntervalEvent] = []
    for record in records:
        events = runner(record["observations"], profile)
        predicted = bool(events)
        rows.append({"record_id": record["record_id"], "ground_truth": record["label"], "predicted_fall": predicted, "events": events})
        temporal_predictions.extend(
            IntervalEvent(f"{record['record_id']}:prediction:{index}", item["start_seconds"], item["end_seconds"], f"potential_fall:{record['record_id']}")
            for index, item in enumerate(events)
        )
        temporal_truth.extend(
            IntervalEvent(f"{record['record_id']}:truth:{index}", item.start_seconds, item.end_seconds, f"potential_fall:{record['record_id']}")
            for index, item in enumerate(record["annotations"])
        )
    def metrics(scope):
        subset = [item for item in rows if scope(item["record_id"])]
        return evaluate_video_predictions([
            VideoPrediction(item["record_id"], item["ground_truth"], item["predicted_fall"], len(item["events"]))
            for item in subset
        ])
    overall = metrics(lambda _: True)
    return {
        "profile": profile,
        "overall": overall,
        "uncertainty_95_wilson": {
            "precision": wilson_interval(overall["true_positives"], overall["true_positives"] + overall["false_positives"]),
            "recall": wilson_interval(overall["true_positives"], overall["true_positives"] + overall["false_negatives"]),
            "false_alert_rate": wilson_interval(overall["false_positives"], overall["false_positives"] + overall["true_negatives"]),
        },
        "calibration": metrics(lambda record_id: record_id in CALIBRATION_IDS),
        "held_out_non_calibration": metrics(lambda record_id: record_id not in CALIBRATION_IDS),
        "temporal_hybrid": evaluate_events(temporal_predictions, temporal_truth, 0.3, 1.0),
        "records": rows,
        "cached_rule_evaluation_seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare fall-rule profiles using cached real MediaPipe outputs.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "external" / "validation" / "reports" / "fall-profile-comparison.json")
    parser.add_argument("--manifest", type=Path, help="Restrict evaluation to original_recording_id values in a prepared manifest.")
    parser.add_argument("--tracked-output", type=Path, default=PROJECT_ROOT / "evaluations" / "fall_detection_profile_comparison.json")
    args = parser.parse_args()
    selected_ids = ORIGINAL_20_IDS
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        selected_ids = {item["original_recording_id"] for item in manifest["records"]}
    db = SessionLocal()
    records = []
    diagnostics = {}
    try:
        for asset in db.scalars(select(DatasetAsset).order_by(DatasetAsset.original_recording_id)):
            if selected_ids is not None and asset.original_recording_id not in selected_ids:
                continue
            pose_rows = db.scalars(select(PoseEvidence).where(PoseEvidence.video_id == asset.video_id).order_by(PoseEvidence.timestamp_seconds)).all()
            observations = load_observations(pose_rows)
            annotations = db.scalars(select(ValidationAnnotation).where(
                ValidationAnnotation.video_id == asset.video_id,
                ValidationAnnotation.event_type == "potential_fall",
                ValidationAnnotation.ground_truth_label == "positive",
            )).all()
            records.append({"record_id": asset.original_recording_id, "label": asset.evaluation_label, "observations": observations, "annotations": annotations})
            if asset.original_recording_id in ROOT_CAUSES:
                series = diagnostic_series(observations)
                diagnostics[asset.original_recording_id] = {
                    "summary": summarize_diagnostics(series),
                    "baseline_events": run_profile(observations, BASELINE_PROFILE),
                    "improved_events": run_profile(observations, IMPROVED_PROFILE),
                    "root_cause": ROOT_CAUSES[asset.original_recording_id],
                    "source_intervals": [{"start_seconds": item.start_seconds, "end_seconds": item.end_seconds, "source": item.annotation_source} for item in annotations],
                    "timeline": series,
                }
    finally:
        db.close()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": "UR Fall Detection selected subset" if selected_ids is not None else "UR Fall Detection balanced 20-video subset",
        "baseline_preserved": True,
        "participant_split_status": "UR sequence files expose no participant/session identifier; participant-disjoint splitting cannot be verified.",
        "calibration_ids": sorted(CALIBRATION_IDS),
        "held_out_warning": "All videos were inspected diagnostically. The non-calibration split is useful for regression only and is not an unbiased generalization estimate.",
        "temporal_scope": f"All predicted events from {len(records)} selected videos are included; positive intervals are source annotations and non-fall video labels act as negative controls.",
        "baseline": evaluate_profile(records, BASELINE_PROFILE),
        "improved": evaluate_profile(records, IMPROVED_PROFILE),
        "motion_fusion": evaluate_profile(records, MOTION_FUSION_PROFILE, lambda observations, profile: [event.__dict__ for event in detect_motion_fusion_events(observations, **{key: value for key, value in profile.items() if key != "name"})]),
        "diagnostics": diagnostics,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    diagnostic_root = args.output.parent / "fall-diagnostics"
    diagnostic_root.mkdir(parents=True, exist_ok=True)
    for record_id, payload in diagnostics.items():
        (diagnostic_root / f"{record_id}.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    sanitized = {
        key: report[key] for key in ("generated_at", "dataset", "baseline_preserved", "participant_split_status", "calibration_ids", "held_out_warning", "temporal_scope")
    }
    for name in ("baseline", "improved", "motion_fusion"):
        sanitized[name] = {key: report[name][key] for key in ("profile", "overall", "uncertainty_95_wilson", "calibration", "held_out_non_calibration", "temporal_hybrid", "cached_rule_evaluation_seconds")}
    tracked = args.tracked_output
    tracked.write_text(json.dumps(sanitized, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({name: report[name]["overall"] for name in ("baseline", "improved", "motion_fusion")}, indent=2))
    print(f"Wrote {args.output} and {tracked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
