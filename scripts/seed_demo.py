"""Create the synthetic video and seed it plus one visibly labeled mock review event."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.core.config import get_settings  # noqa: E402
from app.database.models import CandidateEvent, Video  # noqa: E402
from app.database.session import SessionLocal, init_db  # noqa: E402
from app.services.video_io import probe_video  # noqa: E402


def main():
    demo = ROOT / "runtime" / "demo" / "visionguard_demo.mp4"
    if not demo.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_demo.py")], check=True)
    settings = get_settings()
    init_db()
    db = SessionLocal()
    existing = db.query(Video).filter(Video.original_filename == "visionguard_demo.mp4", Video.is_demo.is_(True)).first()
    if existing:
        print(f"Demo already seeded: {existing.id}")
        return
    video_id = str(uuid4())
    destination = settings.uploads_dir / f"{video_id}.mp4"
    shutil.copy2(demo, destination)
    metadata = probe_video(destination)
    video = Video(
        id=video_id, original_filename="visionguard_demo.mp4", stored_filename=destination.name,
        path=str(destination), mime_type="video/mp4", size_bytes=destination.stat().st_size,
        duration_seconds=metadata["duration_seconds"], width=metadata["width"], height=metadata["height"],
        fps=metadata["fps"], codec=metadata["codec"], status="uploaded", is_demo=True,
    )
    db.add(video)
    db.flush()
    db.add(CandidateEvent(
        video_id=video.id, event_type="synthetic_demo_fixture",
        label="Synthetic Fixture — Potential Exit Obstruction (Not Model Output)",
        start_seconds=4.0, end_seconds=6.0, processing_method="development_seed_fixture",
        model_version="none", raw_scores_json=json.dumps({"mock": True}),
        thresholds_json=json.dumps({"mock": True}), supporting_frames_json="[]",
        review_status="pending", synthetic_fixture=True,
    ))
    db.commit()
    print(f"Seeded demo video: {video.id}")
    print("The review event is explicitly marked synthetic_fixture=true and is not model evidence.")
    db.close()


if __name__ == "__main__":
    main()

