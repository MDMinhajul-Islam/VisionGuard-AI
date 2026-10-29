from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.database.models import ProcessingJob, Video, now_iso
from app.database.session import SessionLocal
from app.vision.video_processor import cleanup_partial_analysis, process_video_job
from app.workers.job_queue import job_queue


def recover_processing_jobs() -> dict[str, int]:
    """Recover queued work and quarantine jobs interrupted by a process exit."""
    recovered = 0
    interrupted = 0
    settings = get_settings()
    with SessionLocal() as db:
        jobs = db.scalars(select(ProcessingJob).where(ProcessingJob.status.in_(["queued", "running"]))).all()
        for job in jobs:
            video = db.get(Video, job.video_id)
            if job.status == "queued":
                job_queue.submit(job.id, process_video_job)
                recovered += 1
                continue
            if video:
                cleanup_partial_analysis(db, video, settings.frames_dir / video.id)
                video.status = "uploaded"
            job.status = "failed"
            job.stage = "interrupted_by_process_exit"
            job.error = "Worker process exited before completion; partial generated artifacts were removed. Retry explicitly."
            job.completed_at = now_iso()
            db.commit()
            interrupted += 1
        db.commit()
    return {"queued_resubmitted": recovered, "running_quarantined": interrupted}
