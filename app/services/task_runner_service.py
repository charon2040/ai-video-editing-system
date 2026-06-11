from __future__ import annotations

import logging

from app.services.task_run_context_service import task_run_context_service
from app.services.task_state_service import task_state_service
from app.services.task_store_service import task_store_service
from app.workflows.task_runtime import task_workflow_runtime_service


logger = logging.getLogger(__name__)


class TaskRunnerService:
    def run_task(self, task_id: str, phase: str = "draft") -> None:
        task = task_store_service.get_task(task_id)
        if not task:
            return

        context = task_run_context_service.build_context(task_id=task_id, task=task)

        try:
            logger.info(
                "Task %s started: file=%s mode=%s phase=%s",
                task_id,
                context.original_filename,
                context.request_mode,
                phase,
            )
            task_workflow_runtime_service.run(
                task=task,
                run_context=context,
                phase=phase,
            )
        except Exception as exc:
            logger.exception("Task %s failed", task_id)
            task_state_service.update_task(
                task_id,
                status="failed",
                stage="failed",
                progress=100,
                message="任务失败",
                error=str(exc),
            )


task_runner_service = TaskRunnerService()
