from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock


class LocalJobQueue:
    """Single-process local queue. SQLite keeps job state; running tasks do not survive process exit."""

    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="visionguard-worker")
        self.futures = {}
        self.lock = Lock()

    def submit(self, job_id: str, function):
        with self.lock:
            self.futures[job_id] = self.executor.submit(function, job_id)

    def active(self, job_id: str) -> bool:
        with self.lock:
            future = self.futures.get(job_id)
            return bool(future and not future.done())


job_queue = LocalJobQueue()

