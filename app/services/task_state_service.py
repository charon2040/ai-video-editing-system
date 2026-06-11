from __future__ import annotations

from typing import Any, Dict

from app.services.task_event_service import now_iso, task_event_service
from app.services.task_store_service import task_store_service


class TaskStateService:
    def list_task_events(self, task_id: str) -> list[Dict[str, Any]]:
        return task_event_service.list_events(task_id)

    def sanitize_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not task:
            return {}
        item = dict(task)
        item.pop("source_path", None)
        item.pop("source_hash", None)
        item.pop("source_size", None)
        payload = dict(item.get("payload", {}) or {})
        payload.pop("uploaded_voiceover_path", None)
        item["payload"] = payload
        return item

    def upsert_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return task_store_service.upsert_task(task)

    def record_task_event(
        self,
        task_id: str,
        *,
        event_type: str = "state_changed",
        task: Dict[str, Any] | None = None,
        message: str = "",
        detail: Dict[str, Any] | None = None,
    ) -> None:
        task_event_service.record(
            task_id,
            event_type=event_type,
            task=task or task_store_service.get_task(task_id),
            message=message,
            detail=detail,
        )

    def update_task(
        self,
        task_id: str,
        *,
        event_type: str = "",
        event_detail: Dict[str, Any] | None = None,
        **patch: Any,
    ) -> Dict[str, Any]:
        task = task_store_service.get_task(task_id)
        if not task:
            return {}

        old_task = dict(task)
        for key, value in patch.items():
            if key in {"artifacts", "result"} and isinstance(value, dict):
                task[key] = {**task.get(key, {}), **value}
            else:
                task[key] = value
        task["updated_at"] = now_iso()
        task_store_service.upsert_task(task)

        tracked_keys = {"status", "stage", "progress", "message", "error"}
        changed = {
            key: {"from": old_task.get(key), "to": task.get(key)}
            for key in tracked_keys
            if key in patch and old_task.get(key) != task.get(key)
        }
        if event_type or changed:
            detail = {"changed": changed}
            if event_detail:
                detail.update(event_detail)
            self.record_task_event(
                task_id,
                event_type=event_type or task_event_service.event_type_from_update(old_task, task, patch),
                task=task,
                detail=detail,
            )
        return self.sanitize_task(task)


task_state_service = TaskStateService()
