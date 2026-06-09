from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List

from app.services.draft_workflow_service import draft_workflow_service
from app.services.task_run_context_service import TaskRunContext


logger = logging.getLogger(__name__)

UpdateTaskCallback = Callable[..., Dict[str, Any]]


class TaskDraftPhaseService:
    def run_draft(
        self,
        *,
        context: TaskRunContext,
        subtitles: List[Dict[str, Any]],
        audio_path: Path,
        asr_cache_hit: bool,
        update_task: UpdateTaskCallback,
    ) -> None:
        task_id = context.task_id
        update_task(
            task_id,
            stage="drafting",
            progress=58,
            message="正在让大模型全文阅读字幕并生成文案初稿",
            artifacts={"audio_url": f"/audio/{audio_path.name}"},
            result={
                "subtitle_count": len(subtitles),
                "asr_cache_hit": asr_cache_hit,
            },
        )
        draft = draft_workflow_service.generate_narration_draft(
            request_text=context.request_text,
            subtitles=subtitles,
            duration_seconds=context.duration_seconds,
            style=context.style,
            project_context=context.project_context,
        )

        update_task(
            task_id,
            status="waiting_review",
            stage="awaiting_script_review",
            progress=68,
            message="文案初稿已生成，请修改确认后继续配音与选片",
            artifacts={"audio_url": f"/audio/{audio_path.name}"},
            result={
                "subtitle_count": len(subtitles),
                "asr_cache_hit": asr_cache_hit,
                "draft_script": draft.script,
                "draft_beats": draft.beats,
                "grounding": draft.grounding,
                "suggestions": draft.suggestions,
                "review_status": "awaiting_review",
                "voiceover_enabled": context.enable_dubbing,
                "voiceover_script": draft.voiceover_script,
            },
        )
        logger.info("Task %s draft ready: beats=%s", task_id, len(draft.beats))


task_draft_phase_service = TaskDraftPhaseService()
