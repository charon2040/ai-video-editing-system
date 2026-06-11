from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.services.task_bootstrap_service import task_bootstrap_service
from app.services.task_lifecycle_service import task_lifecycle_service
from app.services.task_query_service import task_query_service
from app.services.task_review_service import task_review_service
from app.services.task_state_service import task_state_service


class TaskService:
    def __init__(self) -> None:
        task_bootstrap_service.initialize()

    def recover_interrupted_tasks(self) -> int:
        return task_bootstrap_service.recover_interrupted_tasks()

    def list_tasks(self, project_id: str = "", *, user_id: str = "local") -> List[Dict[str, Any]]:
        return task_query_service.list_tasks(project_id=project_id, user_id=user_id)

    def list_task_events(self, task_id: str, *, user_id: str = "local") -> List[Dict[str, Any]]:
        return task_query_service.list_task_events(task_id, user_id=user_id)

    def get_task(self, task_id: str, *, user_id: str = "local") -> Dict[str, Any]:
        return task_query_service.get_task(task_id, user_id=user_id)

    def delete_task(
        self,
        task_id: str,
        *,
        user_id: str = "local",
        delete_source: bool = False,
    ) -> Dict[str, Any]:
        return task_lifecycle_service.delete_task(
            task_id,
            user_id=user_id,
            delete_source=delete_source,
        )

    def delete_finished_tasks(
        self,
        project_id: str = "",
        *,
        user_id: str = "local",
        delete_source: bool = False,
    ) -> Dict[str, Any]:
        return task_lifecycle_service.delete_finished_tasks(
            project_id=project_id,
            user_id=user_id,
            delete_source=delete_source,
        )

    def update_task(
        self,
        task_id: str,
        *,
        event_type: str = "",
        event_detail: Dict[str, Any] | None = None,
        **patch: Any,
    ) -> Dict[str, Any]:
        return task_state_service.update_task(
            task_id,
            event_type=event_type,
            event_detail=event_detail,
            **patch,
        )

    def update_draft(
        self,
        task_id: str,
        *,
        draft_script: str = "",
        draft_beats: List[Dict[str, Any]] | None = None,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        return task_review_service.update_draft(
            task_id,
            draft_script=draft_script,
            draft_beats=draft_beats,
            user_id=user_id,
        )

    def approve_draft(
        self,
        task_id: str,
        *,
        draft_script: str = "",
        draft_beats: List[Dict[str, Any]] | None = None,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        task_review_service.approve_draft(
            task_id,
            draft_script=draft_script,
            draft_beats=draft_beats,
            user_id=user_id,
        )
        return self.get_task(task_id, user_id=user_id)

    def retry_alignment(
        self,
        task_id: str,
        *,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        task_review_service.retry_alignment(task_id, user_id=user_id)
        return self.get_task(task_id, user_id=user_id)

    def create_task(
        self,
        *,
        source_path: Path,
        source_hash: str,
        source_size: int,
        original_filename: str,
        request_text: str,
        request_mode: str,
        project_id: str,
        pipeline_mode: str,
        project_context: str,
        knowledge_policy: str,
        knowledge_base_id: str,
        duration_seconds: int,
        style: str,
        enable_dubbing: bool,
        voice_mode: str,
        voice_profile_id: str,
        tts_voice: str,
        tts_speed: float,
        keep_original_audio: bool,
        voice_source: str = "tts",
        uploaded_voiceover_filename: str = "",
        uploaded_voiceover_content: bytes | None = None,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        return task_lifecycle_service.create_task(
            source_path=source_path,
            source_hash=source_hash,
            source_size=source_size,
            original_filename=original_filename,
            request_text=request_text,
            request_mode=request_mode,
            project_id=project_id,
            pipeline_mode=pipeline_mode,
            project_context=project_context,
            knowledge_policy=knowledge_policy,
            knowledge_base_id=knowledge_base_id,
            duration_seconds=duration_seconds,
            style=style,
            enable_dubbing=enable_dubbing,
            voice_source=voice_source,
            voice_mode=voice_mode,
            voice_profile_id=voice_profile_id,
            tts_voice=tts_voice,
            tts_speed=tts_speed,
            keep_original_audio=keep_original_audio,
            uploaded_voiceover_filename=uploaded_voiceover_filename,
            uploaded_voiceover_content=uploaded_voiceover_content,
            user_id=user_id,
        )

    def create_task_from_existing_source(
        self,
        *,
        base_task_id: str,
        request_text: str,
        request_mode: str,
        project_id: str,
        pipeline_mode: str,
        project_context: str,
        knowledge_policy: str,
        knowledge_base_id: str,
        duration_seconds: int,
        style: str,
        enable_dubbing: bool,
        voice_mode: str,
        voice_profile_id: str,
        tts_voice: str,
        tts_speed: float,
        keep_original_audio: bool,
        voice_source: str = "tts",
        user_id: str = "local",
    ) -> Dict[str, Any]:
        return task_lifecycle_service.create_task_from_existing_source(
            base_task_id=base_task_id,
            request_text=request_text,
            request_mode=request_mode,
            project_id=project_id,
            pipeline_mode=pipeline_mode,
            project_context=project_context,
            knowledge_policy=knowledge_policy,
            knowledge_base_id=knowledge_base_id,
            duration_seconds=duration_seconds,
            style=style,
            enable_dubbing=enable_dubbing,
            voice_source=voice_source,
            voice_mode=voice_mode,
            voice_profile_id=voice_profile_id,
            tts_voice=tts_voice,
            tts_speed=tts_speed,
            keep_original_audio=keep_original_audio,
            user_id=user_id,
        )

    def list_clip_plans(self, task_id: str, *, user_id: str = "local") -> List[Dict[str, Any]]:
        return task_query_service.list_clip_plans(task_id, user_id=user_id)

task_service = TaskService()

