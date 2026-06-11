from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from app.core.db import app_db
from app.core.config import settings
from app.services.media_service import media_service
from app.services.task_artifact_service import task_artifact_service
from app.services.task_factory_service import task_factory_service
from app.services.task_runner_service import task_runner_service
from app.services.task_state_service import task_state_service
from app.services.task_store_service import task_store_service
from app.services.task_worker_service import task_worker_service


logger = logging.getLogger(__name__)


class TaskLifecycleService:
    def _task_can_be_deleted(self, task: Dict[str, Any], *, allow_waiting_review: bool = True) -> bool:
        status = str(task.get("status", "") or "").strip()
        if status in {"completed", "failed"}:
            return True
        return allow_waiting_review and status == "waiting_review"

    def _cleanup_source_and_cache_if_unreferenced(self, task: Dict[str, Any], *, task_id: str) -> Dict[str, Any]:
        source_path = str(task.get("source_path", "") or "").strip()
        source_hash = str(task.get("source_hash", "") or "").strip()
        result: Dict[str, Any] = {
            "deleted_source": False,
            "deleted_asr_cache": False,
            "deleted_asr_cache_record": False,
            "deleted_asr_cache_audio": False,
            "source_reference_count": 0,
            "asr_cache_reference_count": 0,
            "source_retained_reason": "",
            "asr_cache_retained_reason": "",
        }

        if source_path:
            source_reference_count = task_store_service.count_tasks_by_source_path(
                source_path,
                exclude_task_id=task_id,
            )
            result["source_reference_count"] = source_reference_count
            if source_reference_count == 0:
                source_cleanup = task_artifact_service.cleanup_source_file(task)
                result.update(source_cleanup)
                if not result.get("deleted_source"):
                    result["source_retained_reason"] = "源文件不存在，或不在受控 uploads 目录下"
            else:
                result["source_retained_reason"] = "仍有其他任务引用同一源文件"
        else:
            result["source_retained_reason"] = "任务没有记录源文件路径"

        if source_hash:
            asr_reference_count = task_store_service.count_tasks_by_source_hash(
                source_hash,
                exclude_task_id=task_id,
            )
            result["asr_cache_reference_count"] = asr_reference_count
            if asr_reference_count == 0:
                cached = app_db.get_asr_cache(source_hash)
                cache_cleanup = task_artifact_service.cleanup_asr_cache_files(task, cached)
                result.update(cache_cleanup)
                deleted_record = app_db.delete_asr_cache(source_hash)
                result["deleted_asr_cache_record"] = deleted_record
                result["deleted_asr_cache"] = bool(
                    result.get("deleted_asr_cache_audio") or deleted_record
                )
                if not result["deleted_asr_cache"]:
                    result["asr_cache_retained_reason"] = "ASR 缓存不存在或已被清理"
            else:
                result["asr_cache_retained_reason"] = "仍有其他任务引用同一素材哈希"
        else:
            result["asr_cache_retained_reason"] = "任务没有记录素材哈希"

        return result

    def delete_task(
        self,
        task_id: str,
        *,
        user_id: str = "local",
        delete_source: bool = False,
    ) -> Dict[str, Any]:
        task = task_store_service.get_task(task_id, user_id=user_id)
        if not task:
            raise ValueError("Task not found")
        if not self._task_can_be_deleted(task):
            raise ValueError("Only completed, failed, or waiting-review tasks can be deleted")

        result: Dict[str, Any] = {
            "task_id": task_id,
            "deleted": False,
            "delete_source_requested": bool(delete_source),
            "deleted_source": False,
            "deleted_asr_cache": False,
        }
        result.update(task_artifact_service.cleanup_task_runtime_files(task_id))
        if delete_source:
            result.update(self._cleanup_source_and_cache_if_unreferenced(task, task_id=task_id))

        if not task_store_service.delete_task(task_id, user_id=user_id):
            raise ValueError("Task not found")

        result["deleted"] = True
        logger.info(
            "Task deleted: id=%s delete_source=%s source_deleted=%s asr_deleted=%s",
            task_id,
            bool(delete_source),
            bool(result.get("deleted_source")),
            bool(result.get("deleted_asr_cache")),
        )
        return result

    def delete_finished_tasks(
        self,
        project_id: str = "",
        *,
        user_id: str = "local",
        delete_source: bool = False,
    ) -> Dict[str, Any]:
        deleted_ids: List[str] = []
        details: List[Dict[str, Any]] = []
        for task in task_store_service.list_tasks(project_id=project_id, user_id=user_id):
            if not self._task_can_be_deleted(task, allow_waiting_review=False):
                continue
            task_id = str(task.get("id", "") or "").strip()
            if not task_id:
                continue
            result: Dict[str, Any] = {
                "task_id": task_id,
                "delete_source_requested": bool(delete_source),
                "deleted_source": False,
                "deleted_asr_cache": False,
            }
            result.update(task_artifact_service.cleanup_task_runtime_files(task_id))
            if delete_source:
                result.update(self._cleanup_source_and_cache_if_unreferenced(task, task_id=task_id))
            if task_store_service.delete_task(task_id, user_id=user_id):
                deleted_ids.append(task_id)
                result["deleted"] = True
                details.append(result)

        if deleted_ids:
            logger.info("Finished tasks deleted: count=%s project_id=%s", len(deleted_ids), project_id or "*")
        return {
            "deleted": True,
            "deleted_count": len(deleted_ids),
            "task_ids": deleted_ids,
            "delete_source_requested": bool(delete_source),
            "items": details,
        }

    def _attach_uploaded_voiceover(
        self,
        task: Dict[str, Any],
        *,
        filename: str,
        content: bytes | None,
    ) -> Dict[str, Any]:
        payload = dict(task.get("payload", {}) or {})
        if str(payload.get("voice_source", "") or "tts") != "uploaded_voiceover":
            return task
        if not content:
            raise ValueError("上传完整配音模式需要提供配音音频文件。")

        task_id = str(task.get("id", "") or "").strip()
        if not task_id:
            raise ValueError("Task id is missing")

        task_dir = settings.voiceover_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        suffix = "".join(Path(filename or "").suffixes) or ".audio"
        raw_path = task_dir / f"uploaded_voiceover_source{suffix}"
        normalized_path = task_dir / "uploaded_voiceover.wav"
        raw_path.write_bytes(content)
        if not media_service.normalize_voiceover_audio(str(raw_path), str(normalized_path)):
            raise ValueError("上传配音音频规范化失败，请确认文件格式可被 FFmpeg 读取。")
        duration_ms = media_service.probe_duration_ms(str(normalized_path))
        if duration_ms <= 0:
            raise ValueError("上传配音音频没有有效时长。")

        relative_path = f"{task_id}/uploaded_voiceover.wav"
        payload.update(
            {
                "enable_dubbing": True,
                "voice_source": "uploaded_voiceover",
                "voice_profile_label": "上传完整配音",
                "uploaded_voiceover_path": relative_path,
                "uploaded_voiceover_name": str(filename or "uploaded_voiceover"),
                "uploaded_voiceover_duration_ms": duration_ms,
            }
        )
        artifacts = {
            **(task.get("artifacts", {}) or {}),
            "uploaded_voiceover_url": f"/outputs/voiceovers/{relative_path}",
        }
        result = {
            **(task.get("result", {}) or {}),
            "voiceover_enabled": True,
            "uploaded_voiceover_duration_ms": duration_ms,
        }
        return {
            **task,
            "payload": payload,
            "artifacts": artifacts,
            "result": result,
        }

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
        voice_source: str,
        voice_mode: str,
        voice_profile_id: str,
        tts_voice: str,
        tts_speed: float,
        keep_original_audio: bool,
        uploaded_voiceover_filename: str = "",
        uploaded_voiceover_content: bytes | None = None,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        task = task_factory_service.build_task(
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
            user_id=user_id,
        )
        task = self._attach_uploaded_voiceover(
            task,
            filename=uploaded_voiceover_filename,
            content=uploaded_voiceover_content,
        )
        task_id = str(task.get("id", ""))
        payload = task.get("payload", {}) or {}
        task_state_service.upsert_task(task)
        logger.info(
            "Task created: id=%s file=%s mode=%s hash=%s",
            task_id,
            original_filename,
            request_mode,
            source_hash[:12],
        )
        task_state_service.record_task_event(
            task_id,
            event_type="task_created",
            task=task,
            detail={
                "original_filename": original_filename,
                "request_mode": request_mode,
                "style": style,
                "duration_seconds": duration_seconds,
                "enable_dubbing": bool(enable_dubbing),
                "voice_source": str(payload.get("voice_source", "") or "tts"),
                "project_id": str(payload.get("project_id", "") or "default"),
                "project_title": str(payload.get("project_title", "") or ""),
                "pipeline_mode": str(payload.get("pipeline_mode", "") or "narration_clip"),
                "workflow_template_title": str(payload.get("workflow_template_title", "") or ""),
                "voice_mode": str(payload.get("voice_mode", "") or ""),
                "knowledge_policy": str(payload.get("knowledge_policy", "") or "none"),
                "knowledge_used": bool(payload.get("knowledge_used", False)),
                "knowledge_base_id": str(payload.get("knowledge_base_id", "") or ""),
            },
        )

        task_worker_service.start_task(task_id, phase="draft", runner=task_runner_service.run_task)
        return task_state_service.sanitize_task(task)

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
        voice_source: str,
        voice_mode: str,
        voice_profile_id: str,
        tts_voice: str,
        tts_speed: float,
        keep_original_audio: bool,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        base_task = task_store_service.get_task(base_task_id, user_id=user_id)
        if not base_task:
            raise ValueError("Base task not found")

        source_path = Path(base_task.get("source_path", ""))
        if not source_path.exists():
            raise ValueError("Base source video not found")

        original_filename = str(
            base_task.get("payload", {}).get("original_filename", source_path.name)
        )
        source_hash = str(base_task.get("source_hash", "") or "")
        source_size = int(base_task.get("source_size", 0) or source_path.stat().st_size)

        return self.create_task(
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
            user_id=user_id,
        )


task_lifecycle_service = TaskLifecycleService()
