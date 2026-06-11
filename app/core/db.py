from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings
from app.repositories.sqlite_asr_cache_repository import SQLiteASRCacheRepository
from app.repositories.sqlite_clip_plan_repository import SQLiteClipPlanRepository
from app.repositories.sqlite_database_maintenance import SQLiteDatabaseMaintenance
from app.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.repositories.sqlite_project_knowledge_repository import SQLiteProjectKnowledgeRepository
from app.repositories.sqlite_task_repository import SQLiteTaskEventRepository, SQLiteTaskRepository
from app.repositories.sqlite_user_repository import SQLiteUserRepository, SQLiteUserSessionRepository
from app.repositories.sqlite_voice_profile_repository import SQLiteVoiceProfileRepository


class AppDatabase:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        self.maintenance = SQLiteDatabaseMaintenance(self)
        self.tasks = SQLiteTaskRepository(self)
        self.task_events = SQLiteTaskEventRepository(self)
        self.users = SQLiteUserRepository(self)
        self.user_sessions = SQLiteUserSessionRepository(self)
        self.asr_cache = SQLiteASRCacheRepository(self)
        self.clip_plans = SQLiteClipPlanRepository(self)
        self.projects = SQLiteProjectRepository(self)
        self.project_knowledge = SQLiteProjectKnowledgeRepository(self)
        self.voice_profiles = SQLiteVoiceProfileRepository(self)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _connect_external(self, db_path: Path) -> sqlite3.Connection:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        self.maintenance.init_schema()

    def migrate_legacy_tasks(self, legacy_path: Path) -> int:
        return self.maintenance.migrate_legacy_tasks(legacy_path)

    def merge_external_database(self, db_path: Path) -> Dict[str, int]:
        return self.maintenance.merge_external_database(db_path)

    def upsert_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        return self.users.upsert(user)

    def get_user(self, user_id: str) -> Dict[str, Any]:
        return self.users.get(user_id)

    def find_user_by_username(self, username: str) -> Dict[str, Any]:
        return self.users.find_by_username(username)

    def upsert_user_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        return self.user_sessions.upsert(session)

    def get_user_session(self, token_hash: str) -> Dict[str, Any]:
        return self.user_sessions.get(token_hash)

    def delete_user_session(self, token_hash: str) -> bool:
        return self.user_sessions.delete(token_hash)

    def delete_expired_user_sessions(self, now_iso: str) -> int:
        return self.user_sessions.delete_expired(now_iso)

    def get_project(self, project_id: str = "default", *, user_id: str = "local") -> Dict[str, Any]:
        return self.projects.get(project_id, user_id=user_id)

    def list_projects(self, *, user_id: str = "local") -> List[Dict[str, Any]]:
        return self.projects.list(user_id=user_id)

    def upsert_project(self, project: Dict[str, Any]) -> Dict[str, Any]:
        return self.projects.upsert(project)

    def delete_project(self, project_id: str, *, user_id: str = "local") -> bool:
        return self.projects.delete(project_id, user_id=user_id)

    def get_project_knowledge(self, knowledge_id: str = "default", *, user_id: str = "local") -> Dict[str, Any]:
        return self.project_knowledge.get(knowledge_id, user_id=user_id)

    def list_project_knowledge(self, project_id: str = "", *, user_id: str = "local") -> List[Dict[str, Any]]:
        return self.project_knowledge.list(project_id=project_id, user_id=user_id)

    def upsert_project_knowledge(
        self,
        *,
        title: str,
        content: str,
        now_iso: str,
        knowledge_id: str = "default",
        project_id: str = "default",
        user_id: str = "local",
    ) -> Dict[str, Any]:
        return self.project_knowledge.upsert(
            title=title,
            content=content,
            now_iso=now_iso,
            knowledge_id=knowledge_id,
            project_id=project_id,
            user_id=user_id,
        )

    def delete_project_knowledge(self, knowledge_id: str, *, user_id: str = "local") -> bool:
        return self.project_knowledge.delete(knowledge_id, user_id=user_id)

    def list_tasks(self, *, user_id: str = "local") -> List[Dict[str, Any]]:
        return self.tasks.list(user_id=user_id)

    def get_task(self, task_id: str, *, user_id: str = "") -> Dict[str, Any]:
        return self.tasks.get(task_id, user_id=user_id)

    def upsert_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return self.tasks.upsert(task)

    def insert_task_event(
        self,
        *,
        task_id: str,
        event_type: str,
        status: str = "",
        stage: str = "",
        progress: int = 0,
        message: str = "",
        detail: Dict[str, Any] | None = None,
        created_at: str,
    ) -> Dict[str, Any]:
        return self.task_events.insert(
            task_id=task_id,
            event_type=event_type,
            status=status,
            stage=stage,
            progress=progress,
            message=message,
            detail=detail,
            created_at=created_at,
        )

    def list_task_events(self, task_id: str, *, limit: int = 200) -> List[Dict[str, Any]]:
        return self.task_events.list(task_id, limit=limit)

    def delete_task(self, task_id: str, *, user_id: str = "") -> bool:
        return self.tasks.delete(task_id, user_id=user_id)

    def count_tasks_by_source_hash(self, source_hash: str, *, exclude_task_id: str = "") -> int:
        return self.tasks.count_by_source_hash(source_hash, exclude_task_id=exclude_task_id)

    def count_tasks_by_source_path(self, source_path: str, *, exclude_task_id: str = "") -> int:
        return self.tasks.count_by_source_path(source_path, exclude_task_id=exclude_task_id)

    def recover_interrupted_tasks(self, now_iso: str) -> int:
        return self.tasks.recover_interrupted(now_iso)

    def get_asr_cache(self, source_hash: str) -> Dict[str, Any]:
        return self.asr_cache.get(source_hash)

    def upsert_asr_cache(
        self,
        *,
        source_hash: str,
        original_filename: str,
        source_size: int,
        audio_path: str,
        subtitles: List[Dict[str, Any]],
        now_iso: str,
    ) -> None:
        self.asr_cache.upsert(
            source_hash=source_hash,
            original_filename=original_filename,
            source_size=source_size,
            audio_path=audio_path,
            subtitles=subtitles,
            now_iso=now_iso,
        )

    def delete_asr_cache(self, source_hash: str) -> bool:
        return self.asr_cache.delete(source_hash)

    def upsert_clip_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        return self.clip_plans.upsert(plan)

    def list_clip_plans(
        self,
        *,
        task_id: str | None = None,
        source_hash: str | None = None,
        user_id: str = "",
    ) -> List[Dict[str, Any]]:
        return self.clip_plans.list(task_id=task_id, source_hash=source_hash, user_id=user_id)

    def upsert_voice_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        return self.voice_profiles.upsert(profile)

    def get_voice_profile(self, profile_id: str, *, user_id: str = "") -> Dict[str, Any]:
        return self.voice_profiles.get(profile_id, user_id=user_id)

    def find_voice_profile_by_label(self, label: str, *, user_id: str = "") -> Dict[str, Any]:
        return self.voice_profiles.find_by_label(label, user_id=user_id)

    def list_voice_profiles(self, *, active_only: bool = False, user_id: str = "") -> List[Dict[str, Any]]:
        return self.voice_profiles.list(active_only=active_only, user_id=user_id)


app_db = AppDatabase(settings.database_path)
