from __future__ import annotations

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict


logger = logging.getLogger(__name__)


class SQLiteDatabaseMaintenance:
    def __init__(self, database: Any) -> None:
        self._db = database

    def _column_exists(self, conn: Any, table: str, column: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(str(row["name"]) == column for row in rows)

    def _ensure_column(self, conn: Any, table: str, column: str, definition: str) -> None:
        if not self._column_exists(conn, table, column):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def init_schema(self) -> None:
        with self._db._lock, self._db._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    title TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    default_knowledge_base_id TEXT NOT NULL DEFAULT 'default',
                    default_pipeline_mode TEXT NOT NULL DEFAULT 'narration_clip',
                    default_knowledge_policy TEXT NOT NULL DEFAULT 'none',
                    default_duration_seconds INTEGER NOT NULL DEFAULT 0,
                    default_style TEXT NOT NULL DEFAULT 'summary',
                    default_enable_dubbing INTEGER NOT NULL DEFAULT 0,
                    default_voice_mode TEXT NOT NULL DEFAULT 'standard',
                    default_voice_profile_id TEXT NOT NULL DEFAULT '',
                    default_tts_speed REAL NOT NULL DEFAULT 1.0,
                    default_keep_original_audio INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    project_id TEXT NOT NULL DEFAULT 'default',
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    artifacts_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '',
                    source_path TEXT NOT NULL DEFAULT '',
                    source_hash TEXT NOT NULL DEFAULT '',
                    source_size INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS asr_cache (
                    source_hash TEXT PRIMARY KEY,
                    original_filename TEXT NOT NULL,
                    source_size INTEGER NOT NULL DEFAULT 0,
                    audio_path TEXT NOT NULL,
                    subtitles_json TEXT NOT NULL,
                    subtitle_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clip_plans (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    task_id TEXT NOT NULL,
                    source_hash TEXT NOT NULL DEFAULT '',
                    request_text TEXT NOT NULL,
                    request_mode TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    style TEXT NOT NULL DEFAULT '',
                    script TEXT NOT NULL DEFAULT '',
                    suggestions_json TEXT NOT NULL,
                    segments_json TEXT NOT NULL,
                    plan_mode TEXT NOT NULL DEFAULT '',
                    total_duration_ms INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS voice_profiles (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT '',
                    label TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    prompt_text TEXT NOT NULL DEFAULT '',
                    prompt_wav_path TEXT NOT NULL DEFAULT '',
                    language TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL DEFAULT 'seed',
                    is_default INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS project_knowledge (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    project_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL DEFAULT 'state_changed',
                    status TEXT NOT NULL DEFAULT '',
                    stage TEXT NOT NULL DEFAULT '',
                    progress INTEGER NOT NULL DEFAULT 0,
                    message TEXT NOT NULL DEFAULT '',
                    detail_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )
            self._ensure_column(conn, "projects", "user_id", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column(conn, "tasks", "user_id", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column(conn, "clip_plans", "user_id", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column(conn, "voice_profiles", "user_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "project_knowledge", "user_id", "TEXT NOT NULL DEFAULT 'local'")
            self._ensure_column(conn, "tasks", "project_id", "TEXT NOT NULL DEFAULT 'default'")
            self._ensure_column(conn, "project_knowledge", "project_id", "TEXT NOT NULL DEFAULT 'default'")
            self._ensure_column(conn, "projects", "default_knowledge_policy", "TEXT NOT NULL DEFAULT 'none'")
            self._ensure_column(conn, "projects", "default_duration_seconds", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "projects", "default_style", "TEXT NOT NULL DEFAULT 'summary'")
            self._ensure_column(conn, "projects", "default_enable_dubbing", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "projects", "default_voice_mode", "TEXT NOT NULL DEFAULT 'standard'")
            self._ensure_column(conn, "projects", "default_voice_profile_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "projects", "default_tts_speed", "REAL NOT NULL DEFAULT 1.0")
            self._ensure_column(conn, "projects", "default_keep_original_audio", "INTEGER NOT NULL DEFAULT 1")
            now = datetime.now().isoformat(timespec="seconds")
            conn.execute(
                """
                INSERT OR IGNORE INTO project_knowledge (
                    id, user_id, project_id, title, content, created_at, updated_at
                ) VALUES ('default', 'local', 'default', '项目知识库', '', ?, ?)
                """,
                (now, now),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO projects (
                    id, user_id, title, description, default_knowledge_base_id,
                    default_pipeline_mode, default_knowledge_policy,
                    default_duration_seconds, default_style, default_enable_dubbing,
                    default_voice_mode, default_voice_profile_id, default_tts_speed,
                    default_keep_original_audio, created_at, updated_at
                ) VALUES (
                    'default', 'local', '默认项目', '系统自动创建的默认项目', 'default',
                    'narration_clip', 'none', 0, 'summary', 0,
                    'standard', '', 1.0, 1, ?, ?
                )
                """,
                (now, now),
            )
            conn.execute("UPDATE tasks SET project_id = 'default' WHERE project_id IS NULL OR project_id = ''")
            conn.execute("UPDATE tasks SET user_id = 'local' WHERE user_id IS NULL OR user_id = ''")
            conn.execute("UPDATE projects SET user_id = 'local' WHERE user_id IS NULL OR user_id = ''")
            conn.execute("UPDATE project_knowledge SET user_id = 'local' WHERE user_id IS NULL OR user_id = ''")
            conn.execute("UPDATE clip_plans SET user_id = 'local' WHERE user_id IS NULL OR user_id = ''")
            conn.execute(
                "UPDATE voice_profiles SET user_id = '' "
                "WHERE user_id IS NULL OR source_type = 'seed'"
            )
            conn.execute(
                "UPDATE voice_profiles SET user_id = 'local' "
                "WHERE user_id = '' AND source_type != 'seed'"
            )
            conn.execute(
                "UPDATE project_knowledge SET project_id = 'default' "
                "WHERE project_id IS NULL OR project_id = ''"
            )
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(lower(username))")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id, expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project_created ON tasks(project_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_project_created ON tasks(user_id, project_id, created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_source_hash ON tasks(source_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_user_updated ON projects(user_id, updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_project_knowledge_project ON project_knowledge(project_id, updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_project_knowledge_user_project ON project_knowledge(user_id, project_id, updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_plans_task_id ON clip_plans(task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_plans_source_hash ON clip_plans(source_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_plans_user_task ON clip_plans(user_id, task_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_task_events_task_id ON task_events(task_id, id ASC)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_voice_profiles_active_sort "
                "ON voice_profiles(is_active DESC, is_default DESC, sort_order ASC, label ASC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_voice_profiles_user_active_sort "
                "ON voice_profiles(user_id, is_active DESC, is_default DESC, sort_order ASC, label ASC)"
            )
            conn.commit()

    def migrate_legacy_tasks(self, legacy_path: Path) -> int:
        if not legacy_path.exists():
            return 0

        with self._db._lock, self._db._connect() as conn:
            count_row = conn.execute("SELECT COUNT(*) AS total FROM tasks").fetchone()
            if count_row and int(count_row["total"]) > 0:
                return 0

            try:
                items = json.loads(legacy_path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("Failed to read legacy task store: %s", legacy_path)
                return 0

            migrated = 0
            for item in items:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO tasks (
                        id, project_id, status, progress, stage, message,
                        created_at, updated_at,
                        payload_json, artifacts_json, result_json,
                        error, source_path, source_hash, source_size
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item.get("id", "")),
                        "default",
                        str(item.get("status", "queued")),
                        int(item.get("progress", 0) or 0),
                        str(item.get("stage", "queued")),
                        str(item.get("message", "")),
                        str(item.get("created_at", "")),
                        str(item.get("updated_at", "")),
                        json.dumps(item.get("payload", {}), ensure_ascii=False),
                        json.dumps(item.get("artifacts", {}), ensure_ascii=False),
                        json.dumps(item.get("result", {}), ensure_ascii=False),
                        str(item.get("error", "")),
                        "",
                        "",
                        0,
                    ),
                )
                migrated += 1
            conn.commit()
            return migrated

    def merge_external_database(self, db_path: Path) -> Dict[str, int]:
        if not db_path.exists() or db_path.resolve() == self._db._db_path.resolve():
            return {"tasks": 0, "asr_cache": 0, "clip_plans": 0}

        merged = {"tasks": 0, "asr_cache": 0, "clip_plans": 0}
        with self._db._lock, self._db._connect() as conn, self._db._connect_external(db_path) as ext:
            ext_tables = {
                row["name"]
                for row in ext.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }

            if "tasks" in ext_tables:
                rows = ext.execute("SELECT * FROM tasks").fetchall()
                for row in rows:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO tasks (
                            id, project_id, status, progress, stage, message,
                            created_at, updated_at,
                            payload_json, artifacts_json, result_json,
                            error, source_path, source_hash, source_size
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["id"],
                            row["project_id"] if "project_id" in row.keys() else "default",
                            row["status"],
                            int(row["progress"] or 0),
                            row["stage"],
                            row["message"],
                            row["created_at"],
                            row["updated_at"],
                            row["payload_json"],
                            row["artifacts_json"],
                            row["result_json"],
                            row["error"] or "",
                            row["source_path"] if "source_path" in row.keys() else "",
                            row["source_hash"] if "source_hash" in row.keys() else "",
                            int(row["source_size"] or 0) if "source_size" in row.keys() else 0,
                        ),
                    )
                    merged["tasks"] += 1

            if "asr_cache" in ext_tables:
                rows = ext.execute("SELECT * FROM asr_cache").fetchall()
                for row in rows:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO asr_cache (
                            source_hash, original_filename, source_size,
                            audio_path, subtitles_json, subtitle_count,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["source_hash"],
                            row["original_filename"],
                            int(row["source_size"] or 0),
                            row["audio_path"],
                            row["subtitles_json"],
                            int(row["subtitle_count"] or 0),
                            row["created_at"],
                            row["updated_at"],
                        ),
                    )
                    merged["asr_cache"] += 1

            if "clip_plans" in ext_tables:
                rows = ext.execute("SELECT * FROM clip_plans").fetchall()
                for row in rows:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO clip_plans (
                            id, task_id, source_hash, request_text, request_mode,
                            duration_seconds, style, script, suggestions_json,
                            segments_json, plan_mode, total_duration_ms,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row["id"],
                            row["task_id"],
                            row["source_hash"],
                            row["request_text"],
                            row["request_mode"],
                            int(row["duration_seconds"] or 0),
                            row["style"] or "",
                            row["script"] or "",
                            row["suggestions_json"],
                            row["segments_json"],
                            row["plan_mode"] or "",
                            int(row["total_duration_ms"] or 0),
                            row["created_at"],
                            row["updated_at"],
                        ),
                    )
                    merged["clip_plans"] += 1

            conn.commit()
        return merged
