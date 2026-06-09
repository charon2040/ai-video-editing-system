from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings
from app.domain.schemas import TaskArtifacts, TaskPayload, TaskRecord, TaskResult
from app.services.project_knowledge_service import project_knowledge_service
from app.services.project_service import project_service
from app.services.task_event_service import now_iso
from app.services.voice_binding_service import voice_binding_service
from app.workflows import workflow_registry


class TaskFactoryService:
    def build_task(
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
        voice_source: str,
        voice_mode: str,
        voice_profile_id: str,
        tts_voice: str,
        tts_speed: float,
        keep_original_audio: bool,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        normalized_user_id = str(user_id or "local").strip() or "local"
        task_id = uuid.uuid4().hex[:12]
        project = project_service.get_project(project_id, user_id=normalized_user_id)
        effective_project_id = str(project.get("id", "") or "default")
        normalized_pipeline_mode = workflow_registry.normalize_template_id(
            pipeline_mode or str(project.get("default_pipeline_mode", "") or "")
        )
        workflow_template = workflow_registry.get_template(normalized_pipeline_mode)

        requested_policy = str(knowledge_policy or "").strip().lower()
        if requested_policy not in {"none", "project_default", "selected"}:
            requested_policy = "selected" if str(knowledge_base_id or "").strip() else "none"

        if requested_policy == "none":
            effective_knowledge_base_id = ""
        elif requested_policy == "project_default":
            project_knowledge_service.list_project_knowledge(effective_project_id, user_id=normalized_user_id)
            project = project_service.get_project(effective_project_id, user_id=normalized_user_id)
            effective_knowledge_base_id = str(project.get("default_knowledge_base_id", "") or "").strip()
            if not effective_knowledge_base_id:
                raise ValueError("Project has no default knowledge base")
        else:
            effective_knowledge_base_id = str(knowledge_base_id or "").strip()
            if not effective_knowledge_base_id:
                raise ValueError("Missing selected knowledge base")

        context_payload = project_knowledge_service.build_effective_project_context(
            project_context,
            knowledge_base_id=effective_knowledge_base_id,
            project_id=effective_project_id,
            user_id=normalized_user_id,
        )
        normalized_voice_source = str(voice_source or "tts").strip().lower()
        if normalized_voice_source not in {"tts", "uploaded_voiceover"}:
            normalized_voice_source = "tts"
        normalized_enable_dubbing = bool(enable_dubbing) or normalized_voice_source == "uploaded_voiceover"

        if normalized_voice_source == "uploaded_voiceover":
            voice_binding = {
                "voice_profile_id": "",
                "voice_profile_label": "上传完整配音",
                "tts_voice": "",
            }
            normalized_voice_mode = "standard"
        else:
            voice_binding = voice_binding_service.resolve_payload(
                voice_mode=voice_mode,
                voice_profile_id=voice_profile_id,
                tts_voice=tts_voice,
                user_id=normalized_user_id,
            )
            normalized_voice_mode = voice_binding_service.infer_voice_mode(
                voice_mode=voice_mode,
                voice_profile_id=voice_profile_id,
                tts_voice=tts_voice,
                user_id=normalized_user_id,
            )

        now = now_iso()
        task = TaskRecord(
            id=task_id,
            user_id=normalized_user_id,
            status="queued",
            progress=0,
            stage="queued",
            message="任务已创建，等待处理",
            created_at=now,
            updated_at=now,
            project_id=effective_project_id,
            payload=TaskPayload(
                original_filename=original_filename,
                request_text=request_text,
                request_mode=request_mode,
                project_id=effective_project_id,
                project_title=str(project.get("title", "") or "默认项目"),
                project_default_knowledge_base_id=str(project.get("default_knowledge_base_id", "") or ""),
                pipeline_mode=normalized_pipeline_mode,
                workflow_template_title=workflow_template.title if workflow_template else normalized_pipeline_mode,
                knowledge_policy=requested_policy,
                knowledge_used=bool(effective_knowledge_base_id),
                project_context=context_payload["project_context"],
                project_context_extra=context_payload["project_context_extra"],
                knowledge_base_id=context_payload["knowledge_base_id"],
                knowledge_base_title=context_payload["knowledge_base_title"],
                knowledge_base_context=context_payload["knowledge_base_context"],
                knowledge_base_updated_at=context_payload["knowledge_base_updated_at"],
                duration_seconds=duration_seconds,
                style=style,
                enable_dubbing=normalized_enable_dubbing,
                voice_source=normalized_voice_source if normalized_enable_dubbing else "tts",
                voice_mode=normalized_voice_mode,
                voice_profile_id=voice_binding["voice_profile_id"],
                voice_profile_label=voice_binding["voice_profile_label"],
                tts_voice=voice_binding["tts_voice"],
                tts_speed=float(tts_speed or settings.tts_speed_default),
                keep_original_audio=bool(keep_original_audio),
            ),
            artifacts=TaskArtifacts(source_video_url=f"/uploads/{source_path.name}"),
            result=TaskResult(voiceover_enabled=normalized_enable_dubbing),
            error="",
            source_path=str(source_path),
            source_hash=source_hash,
            source_size=int(source_size or 0),
        )
        return task.to_payload()


task_factory_service = TaskFactoryService()
