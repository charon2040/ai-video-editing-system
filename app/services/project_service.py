from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List

from app.core.db import app_db
from app.workflows import workflow_registry


DEFAULT_PROJECT_ID = "default"
DEFAULT_PIPELINE_MODE = "narration_clip"
DEFAULT_STYLE = "summary"
DEFAULT_VOICE_MODE = "standard"


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_project_id(project_id: str = "") -> str:
    return str(project_id or DEFAULT_PROJECT_ID).strip() or DEFAULT_PROJECT_ID


def default_project_id_for_user(user_id: str = "local") -> str:
    normalized_user_id = str(user_id or "local").strip() or "local"
    return DEFAULT_PROJECT_ID if normalized_user_id == "local" else f"{normalized_user_id}_default"


def _normalize_pipeline_mode(value: str = "") -> str:
    return workflow_registry.normalize_template_id(value or DEFAULT_PIPELINE_MODE)


def _normalize_knowledge_policy(value: str = "") -> str:
    policy = str(value or "none").strip().lower()
    return policy if policy in {"none", "project_default", "selected"} else "none"


def _normalize_style(value: str = "") -> str:
    style = str(value or DEFAULT_STYLE).strip().lower()
    return style if style in {"summary", "highlight", "analysis", "short_hook"} else DEFAULT_STYLE


def _normalize_voice_mode(value: str = "") -> str:
    mode = str(value or DEFAULT_VOICE_MODE).strip().lower()
    return mode if mode in {"standard", "clone"} else DEFAULT_VOICE_MODE


def _normalize_duration_seconds(value: int | str | None = 0) -> int:
    try:
        parsed = int(value or 0)
    except Exception:
        parsed = 0
    return max(0, min(600, parsed))


def _normalize_tts_speed(value: float | str | None = 1.0) -> float:
    try:
        parsed = float(value or 1.0)
    except Exception:
        parsed = 1.0
    return max(0.5, min(2.0, parsed))


class ProjectService:
    def ensure_default_project(self, user_id: str = "local") -> Dict:
        normalized_user_id = str(user_id or "local").strip() or "local"
        default_project_id = default_project_id_for_user(normalized_user_id)
        default_knowledge_id = "default" if normalized_user_id == "local" else f"{default_project_id}_kb"
        project = app_db.get_project(default_project_id, user_id=normalized_user_id)
        if project:
            return project
        now = _now_iso()
        project = app_db.upsert_project(
            {
                "id": default_project_id,
                "user_id": normalized_user_id,
                "title": "默认项目",
                "description": "系统自动创建的默认项目",
                "default_knowledge_base_id": default_knowledge_id,
                "default_pipeline_mode": DEFAULT_PIPELINE_MODE,
                "default_knowledge_policy": "none",
                "default_duration_seconds": 0,
                "default_style": DEFAULT_STYLE,
                "default_enable_dubbing": False,
                "default_voice_mode": DEFAULT_VOICE_MODE,
                "default_voice_profile_id": "",
                "default_tts_speed": 1.0,
                "default_keep_original_audio": True,
                "created_at": now,
                "updated_at": now,
            }
        )
        app_db.upsert_project_knowledge(
            title="项目知识库",
            content="",
            now_iso=now,
            knowledge_id=default_knowledge_id,
            project_id=default_project_id,
            user_id=normalized_user_id,
        )
        return project

    def list_projects(self, *, user_id: str = "local") -> List[Dict]:
        self.ensure_default_project(user_id)
        items = app_db.list_projects(user_id=user_id)
        return items or [self.ensure_default_project(user_id)]

    def get_project(self, project_id: str = DEFAULT_PROJECT_ID, *, user_id: str = "local") -> Dict:
        normalized_user_id = str(user_id or "local").strip() or "local"
        normalized_id = _normalize_project_id(project_id)
        if normalized_id == DEFAULT_PROJECT_ID and normalized_user_id != "local":
            normalized_id = default_project_id_for_user(normalized_user_id)
        project = app_db.get_project(normalized_id, user_id=normalized_user_id)
        if project:
            return project
        if normalized_id == default_project_id_for_user(normalized_user_id):
            return self.ensure_default_project(normalized_user_id)
        raise ValueError("Project not found")

    def create_project(
        self,
        *,
        title: str = "",
        description: str = "",
        default_knowledge_base_id: str = "default",
        default_pipeline_mode: str = DEFAULT_PIPELINE_MODE,
        default_knowledge_policy: str = "none",
        default_duration_seconds: int = 0,
        default_style: str = DEFAULT_STYLE,
        default_enable_dubbing: bool = False,
        default_voice_mode: str = DEFAULT_VOICE_MODE,
        default_voice_profile_id: str = "",
        default_tts_speed: float = 1.0,
        default_keep_original_audio: bool = True,
        user_id: str = "local",
    ) -> Dict:
        normalized_user_id = str(user_id or "local").strip() or "local"
        project_id = f"project_{uuid.uuid4().hex[:10]}"
        normalized_title = str(title or "新项目").strip() or "新项目"
        normalized_default_knowledge_base_id = str(default_knowledge_base_id or "").strip()
        should_create_default_knowledge = not normalized_default_knowledge_base_id or normalized_default_knowledge_base_id == "default"
        if should_create_default_knowledge:
            normalized_default_knowledge_base_id = f"{project_id}_default_kb"

        project = self.update_project(
            project_id=project_id,
            title=normalized_title,
            description=description,
            default_knowledge_base_id=normalized_default_knowledge_base_id,
            default_pipeline_mode=default_pipeline_mode,
            default_knowledge_policy=default_knowledge_policy,
            default_duration_seconds=default_duration_seconds,
            default_style=default_style,
            default_enable_dubbing=default_enable_dubbing,
            default_voice_mode=default_voice_mode,
            default_voice_profile_id=default_voice_profile_id,
            default_tts_speed=default_tts_speed,
            default_keep_original_audio=default_keep_original_audio,
            user_id=normalized_user_id,
            allow_create=True,
            allow_missing_default_knowledge=should_create_default_knowledge,
        )
        if should_create_default_knowledge:
            app_db.upsert_project_knowledge(
                title=f"{normalized_title}知识库",
                content="",
                now_iso=_now_iso(),
                knowledge_id=normalized_default_knowledge_base_id,
                project_id=project_id,
                user_id=normalized_user_id,
            )
        return self.get_project(project["id"], user_id=normalized_user_id)

    def delete_project(self, project_id: str, *, user_id: str = "local") -> Dict:
        normalized_user_id = str(user_id or "local").strip() or "local"
        normalized_id = _normalize_project_id(project_id)
        if normalized_id == DEFAULT_PROJECT_ID and normalized_user_id != "local":
            normalized_id = default_project_id_for_user(normalized_user_id)

        default_project_id = default_project_id_for_user(normalized_user_id)
        if normalized_id == default_project_id:
            raise ValueError("Default project cannot be deleted")

        project = app_db.get_project(normalized_id, user_id=normalized_user_id)
        if not project:
            raise ValueError("Project not found")

        linked_tasks = [
            task for task in app_db.list_tasks(user_id=normalized_user_id)
            if str(task.get("project_id") or task.get("payload", {}).get("project_id") or DEFAULT_PROJECT_ID) == normalized_id
        ]
        if linked_tasks:
            raise RuntimeError(
                f"Project still has {len(linked_tasks)} task(s). Delete project tasks first."
            )

        deleted_knowledge_ids: List[str] = []
        for item in app_db.list_project_knowledge(normalized_id, user_id=normalized_user_id):
            knowledge_id = str(item.get("id", "") or "").strip()
            if knowledge_id and app_db.delete_project_knowledge(knowledge_id, user_id=normalized_user_id):
                deleted_knowledge_ids.append(knowledge_id)

        if not app_db.delete_project(normalized_id, user_id=normalized_user_id):
            raise ValueError("Project not found")

        replacement_project = self.ensure_default_project(normalized_user_id)
        return {
            "deleted": True,
            "id": normalized_id,
            "replacement_project_id": str(replacement_project.get("id", "") or default_project_id),
            "deleted_knowledge_ids": deleted_knowledge_ids,
            "items": self.list_projects(user_id=normalized_user_id),
        }

    def update_project(
        self,
        *,
        project_id: str = DEFAULT_PROJECT_ID,
        title: str | None = None,
        description: str | None = None,
        default_knowledge_base_id: str | None = None,
        default_pipeline_mode: str | None = None,
        default_knowledge_policy: str | None = None,
        default_duration_seconds: int | str | None = None,
        default_style: str | None = None,
        default_enable_dubbing: bool | None = None,
        default_voice_mode: str | None = None,
        default_voice_profile_id: str | None = None,
        default_tts_speed: float | str | None = None,
        default_keep_original_audio: bool | None = None,
        user_id: str = "local",
        allow_create: bool = False,
        allow_missing_default_knowledge: bool = False,
    ) -> Dict:
        normalized_user_id = str(user_id or "local").strip() or "local"
        normalized_id = _normalize_project_id(project_id)
        if normalized_id == DEFAULT_PROJECT_ID and normalized_user_id != "local":
            normalized_id = default_project_id_for_user(normalized_user_id)
        now = _now_iso()
        existing = app_db.get_project(normalized_id, user_id=normalized_user_id)
        if normalized_id == default_project_id_for_user(normalized_user_id) and not existing:
            existing = self.ensure_default_project(normalized_user_id)
        if normalized_id != default_project_id_for_user(normalized_user_id) and not existing and not allow_create:
            raise ValueError("Project not found")
        normalized_title = (
            str(title or "").strip()
            if title is not None and str(title or "").strip()
            else str(existing.get("title", "") or "默认项目").strip()
        )
        normalized_description = (
            str(description or "").strip()
            if description is not None
            else str(existing.get("description", "") or "").strip()
        )
        normalized_default_knowledge_base_id = (
            str(default_knowledge_base_id or "").strip()
            if default_knowledge_base_id is not None and str(default_knowledge_base_id or "").strip()
            else str(existing.get("default_knowledge_base_id", "") or "default").strip()
        )
        normalized_pipeline_mode = _normalize_pipeline_mode(
            str(default_pipeline_mode or "").strip()
            if default_pipeline_mode is not None and str(default_pipeline_mode or "").strip()
            else str(existing.get("default_pipeline_mode", "") or DEFAULT_PIPELINE_MODE)
        )
        normalized_knowledge_policy = _normalize_knowledge_policy(
            str(default_knowledge_policy or "").strip()
            if default_knowledge_policy is not None
            else str(existing.get("default_knowledge_policy", "") or "none")
        )
        normalized_duration_seconds = _normalize_duration_seconds(
            default_duration_seconds
            if default_duration_seconds is not None
            else existing.get("default_duration_seconds", 0)
        )
        normalized_style = _normalize_style(
            str(default_style or "").strip()
            if default_style is not None
            else str(existing.get("default_style", "") or DEFAULT_STYLE)
        )
        normalized_enable_dubbing = (
            bool(default_enable_dubbing)
            if default_enable_dubbing is not None
            else bool(existing.get("default_enable_dubbing", False))
        )
        normalized_voice_mode = _normalize_voice_mode(
            str(default_voice_mode or "").strip()
            if default_voice_mode is not None
            else str(existing.get("default_voice_mode", "") or DEFAULT_VOICE_MODE)
        )
        normalized_voice_profile_id = (
            str(default_voice_profile_id or "").strip()
            if default_voice_profile_id is not None
            else str(existing.get("default_voice_profile_id", "") or "").strip()
        )
        normalized_tts_speed = _normalize_tts_speed(
            default_tts_speed
            if default_tts_speed is not None
            else existing.get("default_tts_speed", 1.0)
        )
        normalized_keep_original_audio = (
            bool(default_keep_original_audio)
            if default_keep_original_audio is not None
            else existing.get("default_keep_original_audio", True) is not False
        )
        if normalized_knowledge_policy == "project_default" and not normalized_default_knowledge_base_id:
            raise ValueError("Project default knowledge policy requires a default knowledge base")
        if default_knowledge_base_id is not None and normalized_default_knowledge_base_id:
            knowledge = app_db.get_project_knowledge(
                normalized_default_knowledge_base_id,
                user_id=normalized_user_id,
            )
            knowledge_exists = bool(str(knowledge.get("created_at", "") or knowledge.get("updated_at", "") or "").strip())
            knowledge_project_id = str(knowledge.get("project_id", "") or DEFAULT_PROJECT_ID)
            if (
                not knowledge_exists
                and normalized_default_knowledge_base_id != "default"
                and not allow_missing_default_knowledge
            ):
                raise ValueError("Default knowledge base not found")
            if knowledge_exists and knowledge_project_id != normalized_id:
                raise ValueError("Default knowledge base does not belong to the project")
        project = app_db.upsert_project(
            {
                "id": normalized_id,
                "user_id": normalized_user_id,
                "title": normalized_title or "默认项目",
                "description": normalized_description,
                "default_knowledge_base_id": normalized_default_knowledge_base_id or "default",
                "default_pipeline_mode": normalized_pipeline_mode,
                "default_knowledge_policy": normalized_knowledge_policy,
                "default_duration_seconds": normalized_duration_seconds,
                "default_style": normalized_style,
                "default_enable_dubbing": normalized_enable_dubbing,
                "default_voice_mode": normalized_voice_mode,
                "default_voice_profile_id": normalized_voice_profile_id,
                "default_tts_speed": normalized_tts_speed,
                "default_keep_original_audio": normalized_keep_original_audio,
                "created_at": str(existing.get("created_at", "") or now),
                "updated_at": now,
            }
        )
        return project


project_service = ProjectService()
