from __future__ import annotations

import logging
import threading
from typing import Callable


logger = logging.getLogger(__name__)

TaskRunner = Callable[[str, str], None]


class TaskWorkerService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_workers: set[str] = set()

    def start_task(self, task_id: str, *, phase: str, runner: TaskRunner) -> bool:
        worker_key = f"{task_id}:{phase}"
        with self._lock:
            if worker_key in self._active_workers:
                logger.warning("Worker already running: %s", worker_key)
                return False
            self._active_workers.add(worker_key)

        def _target() -> None:
            try:
                runner(task_id, phase)
            finally:
                with self._lock:
                    self._active_workers.discard(worker_key)

        worker = threading.Thread(target=_target, daemon=True)
        worker.start()
        return True

    def active_worker_count(self) -> int:
        with self._lock:
            return len(self._active_workers)


task_worker_service = TaskWorkerService()
