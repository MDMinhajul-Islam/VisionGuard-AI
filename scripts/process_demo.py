"""Run the full real-model pipeline synchronously on the synthetic demo."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.database.models import ProcessingJob, SafetyZone, Video  # noqa: E402
from app.database.session import SessionLocal, init_db  # noqa: E402
from app.schemas.api import ProcessRequest  # noqa: E402
from app.vision.video_processor import process_video_job  # noqa: E402


def main():
    init_db()
    db = SessionLocal()
    video = db.query(Video).filter(Video.is_demo.is_(True)).first()
    if not video:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo.py")], check=True)
        db.expire_all()
        video = db.query(Video).filter(Video.is_demo.is_(True)).first()
    zone = db.query(SafetyZone).filter(SafetyZone.video_id == video.id).first()
    if not zone:
        zone = SafetyZone(
            video_id=video.id, name="Synthetic Demo Exit Zone", zone_type="emergency_exit",
            polygon_json=json.dumps([[.72, .28], [.94, .28], [.94, .92], [.72, .92]]),
        )
        db.add(zone)
    request = ProcessRequest(
        clip_sample_seconds=1.0, analysis_fps=2.0, pose_fps=5.0,
        process_width=640, detection_threshold=.35,
        enable_clip=True, enable_detection=True, enable_pose=True,
    )
    job = ProcessingJob(video_id=video.id, config_json=request.model_dump_json())
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()
    print(f"Processing job: {job_id}")
    process_video_job(job_id)
    db = SessionLocal()
    job = db.get(ProcessingJob, job_id)
    print(f"Status: {job.status}")
    print(f"Stage: {job.stage}")
    print(f"Metrics: {job.metrics_json}")
    if job.error:
        print(f"Error: {job.error}")
        raise SystemExit(1)
    db.close()


if __name__ == "__main__":
    main()

