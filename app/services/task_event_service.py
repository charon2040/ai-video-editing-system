from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from app.core.db import app_db


logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class TaskEventService:
    def list_events(self, task_id: str) -> List[Dict[str, Any]]:
        return app_db.list_task_events(task_id)

    def event_type_from_update(
        self,
        old_task: Dict[str, Any],
        new_task: Dict[str, Any],
        patch: Dict[str, Any],
    ) -> str:
        if new_task.get("status") == "completed":
            return "task_completed"
        if new_task.get("status") == "failed":
            return "task_failed"
        if new_task.get("status") == "waiting_review":
            return "draft_ready"
        stage = str(new_task.get("stage", "") or "")
        if stage and stage != str(old_task.get("stage", "") or ""):
            return f"stage_{stage}"
        if "message" in patch or "progress" in patch:
            return "progress_updated"
        return "state_changed"

    def record(
        self,
        task_id: str,
        *,
        event_type: str = "state_changed",
        task: Dict[str, Any] | None = None,
        message: str = "",
        detail: Dict[str, Any] | None = None,
    ) -> None:
        try:
            if not task:
                return
            app_db.insert_task_event(
                task_id=task_id,
                event_type=event_type,
                status=str(task.get("status", "") or ""),
                stage=str(task.get("stage", "") or ""),
                progress=int(task.get("progress", 0) or 0),
                message=message or str(task.get("message", "") or ""),
                detail=detail or {},
                created_at=now_iso(),
            )
        except Exception:
            logger.exception("Failed to record task event: task_id=%s event_type=%s", task_id, event_type)


task_event_service = TaskEventService()
