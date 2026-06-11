from __future__ import annotations

from typing import Any, Dict, List

from app.services.clip_plan_service import clip_plan_service
from app.services.task_state_service import task_state_service
from app.services.task_store_service import task_store_service


class TaskQueryService:
    def list_tasks(self, project_id: str = "", *, user_id: str = "local") -> List[Dict[str, Any]]:
        return [
            task_state_service.sanitize_task(item)
            for item in task_store_service.list_tasks(project_id=project_id, user_id=user_id)
        ]

    def list_task_events(self, task_id: str, *, user_id: str = "local") -> List[Dict[str, Any]]:
        if not task_store_service.get_task(task_id, user_id=user_id):
            return []
        return task_state_service.list_task_events(task_id)

    def get_task(self, task_id: str, *, user_id: str = "local") -> Dict[str, Any]:
        self.ensure_plan_metadata(task_id, user_id=user_id)
        return task_state_service.sanitize_task(task_store_service.get_task(task_id, user_id=user_id))

    def list_clip_plans(self, task_id: str, *, user_id: str = "local") -> List[Dict[str, Any]]:
        task = task_store_service.get_task(task_id, user_id=user_id)
        if not task:
            return []
        self.ensure_plan_metadata(task_id, user_id=user_id)
        updated_task = task_store_service.get_task(task_id, user_id=user_id) or task
        return clip_plan_service.list_clip_plans_for_task(updated_task)

    def ensure_plan_metadata(self, task_id: str, *, user_id: str = "local") -> None:
        task = task_store_service.get_task(task_id, user_id=user_id)
        result_patch = clip_plan_service.ensure_plan_metadata(task)
        if result_patch:
            task_state_service.update_task(task_id, result=result_patch)


task_query_service = TaskQueryService()
