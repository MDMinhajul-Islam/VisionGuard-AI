from __future__ import annotations

from sqlalchemy import select, text

from app.core.config import get_settings
from app.database.models import ProcessingJob, Video, now_iso
from app.database.session import SessionLocal, bind_job_context, engine
from app.vision.video_processor import cleanup_partial_analysis, process_video_job
from app.workers.job_queue import job_queue


def recover_processing_jobs() -> dict[str, int]:
    """Recover queued work and quarantine jobs interrupted by a process exit."""
    recovered = 0
    interrupted = 0
    settings = get_settings()
    with SessionLocal() as discovery_db:
        if engine.dialect.name == "postgresql":
            job_ids = list(discovery_db.scalars(text("SELECT job_id FROM visionguard_context.recoverable_job_ids()")))
        else:
            job_ids = list(discovery_db.scalars(select(ProcessingJob.id).where(ProcessingJob.status.in_(["queued", "running"]))))
    for job_id in job_ids:
        with SessionLocal() as db:
            bind_job_context(db, job_id)
            job = db.get(ProcessingJob, job_id)
            if not job:
                continue
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
    return {"queued_resubmitted": recovered, "running_quarantined": interrupted}
