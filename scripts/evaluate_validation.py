"""Run documented one-to-one event metrics against local ground truth."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.database.models import CandidateEvent, ValidationAnnotation  # noqa: E402
from app.database.session import SessionLocal  # noqa: E402
from app.evaluation.metrics import IntervalEvent, evaluate_events  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--event-type", choices=["potential_fall", "potential_exit_obstruction", "potential_walkway_obstruction"], required=True)
    parser.add_argument("--split", default="evaluation", choices=["development", "calibration", "evaluation"])
    parser.add_argument("--iou", type=float, default=.3)
    parser.add_argument("--onset-tolerance", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    db = SessionLocal()
    truth_rows = db.query(ValidationAnnotation).filter_by(video_id=args.video_id, event_type=args.event_type, split=args.split, ground_truth_label="positive").all()
    prediction_rows = db.query(CandidateEvent).filter_by(video_id=args.video_id, event_type=args.event_type, synthetic_fixture=False).all()
    report = evaluate_events(
        [IntervalEvent(item.id, item.start_seconds, item.end_seconds, item.event_type) for item in prediction_rows],
        [IntervalEvent(item.id, item.start_seconds, item.end_seconds, item.event_type) for item in truth_rows],
        args.iou, args.onset_tolerance,
    )
    report.update({
        "video_id": args.video_id, "event_type": args.event_type, "split": args.split,
        "prediction_count": len(prediction_rows), "positive_ground_truth_count": len(truth_rows),
        "warning": "Small local-set metrics do not establish generalization or operational safety.",
    })
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)
    db.close()


if __name__ == "__main__":
    main()
