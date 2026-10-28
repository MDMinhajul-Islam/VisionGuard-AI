"""Validate and import ground-truth annotations without mixing them with predictions."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.database.models import ValidationAnnotation, Video  # noqa: E402
from app.database.session import SessionLocal, init_db  # noqa: E402
from app.evaluation.annotations import deterministic_annotation_id, load_manifest  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--video-id", help="Replace manifest video_id values; useful for local generated IDs")
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    init_db()
    db = SessionLocal()
    imported = 0
    for source in manifest.annotations:
        annotation = source.model_copy(update={"video_id": args.video_id}) if args.video_id else source
        video = db.get(Video, annotation.video_id)
        if not video:
            raise SystemExit(f"Unknown local video_id: {annotation.video_id}")
        if video.duration_seconds and annotation.end_seconds > video.duration_seconds + 1e-6:
            raise SystemExit(f"Annotation exceeds video duration: {annotation}")
        identifier = deterministic_annotation_id(annotation)
        if not db.get(ValidationAnnotation, identifier):
            db.add(ValidationAnnotation(id=identifier, **annotation.model_dump()))
            imported += 1
    db.commit()
    print(f"Validated {len(manifest.annotations)} annotations; imported {imported}.")
    print(f"Dataset: {manifest.dataset_name}; exhaustive={manifest.exhaustive_annotations}")
    db.close()


if __name__ == "__main__":
    main()
