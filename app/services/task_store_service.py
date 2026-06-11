from __future__ import annotations

from typing import Any, Dict, List

from app.core.config import settings
from app.core.db import app_db


class TaskStoreService:
    def _task_project_id(self, task: Dict[str, Any]) -> str:
        payload = task.get("payload", {}) if isinstance(task, dict) else {}
        return str(task.get("project_id") or payload.get("project_id") or "default").strip() or "default"

    def initialize_storage(self) -> Dict[str, Any]:
        app_db.init_schema()
        migrated = app_db.migrate_legacy_tasks(settings.task_store_path)
        merged = app_db.merge_external_database(settings.misplaced_database_path)
        return {
            "migrated_legacy_tasks": migrated,
            "merged_external_database": merged,
        }

    def recover_interrupted_tasks(self, now_iso: str) -> int:
        return app_db.recover_interrupted_tasks(now_iso)

    def list_tasks(self, project_id: str = "", *, user_id: str = "local") -> List[Dict[str, Any]]:
        tasks = app_db.list_tasks(user_id=user_id)
        normalized_project_id = str(project_id or "").strip()
        if not normalized_project_id:
            return tasks
        return [task for task in tasks if self._task_project_id(task) == normalized_project_id]

    def get_task(self, task_id: str, *, user_id: str = "") -> Dict[str, Any]:
        return app_db.get_task(task_id, user_id=user_id)

    def upsert_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return app_db.upsert_task(task)

    def delete_task(self, task_id: str, *, user_id: str = "") -> bool:
        return app_db.delete_task(task_id, user_id=user_id)

    def count_tasks_by_source_hash(self, source_hash: str, *, exclude_task_id: str = "") -> int:
        return app_db.count_tasks_by_source_hash(source_hash, exclude_task_id=exclude_task_id)

    def count_tasks_by_source_path(self, source_path: str, *, exclude_task_id: str = "") -> int:
        return app_db.count_tasks_by_source_path(source_path, exclude_task_id=exclude_task_id)


task_store_service = TaskStoreService()
