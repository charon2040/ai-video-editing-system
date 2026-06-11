from __future__ import annotations

from typing import Any, Dict, List

from app.repositories.row_mappers import row_to_project


class SQLiteProjectRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def get(self, project_id: str = "default", *, user_id: str = "local") -> Dict[str, Any]:
        normalized_id = str(project_id or "default").strip() or "default"
        normalized_user_id = str(user_id or "local").strip() or "local"
        with self._db._lock, self._db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ? AND user_id = ?",
                (normalized_id, normalized_user_id),
            ).fetchone()
        return row_to_project(row)

    def list(self, *, user_id: str = "local") -> List[Dict[str, Any]]:
        normalized_user_id = str(user_id or "local").strip() or "local"
        with self._db._lock, self._db._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM projects
                WHERE user_id = ?
                ORDER BY updated_at DESC, title ASC
                """,
                (normalized_user_id,),
            ).fetchall()
        return [row_to_project(row) for row in rows]

    def upsert(self, project: Dict[str, Any]) -> Dict[str, Any]:
        with self._db._lock, self._db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO projects (
                    id, user_id, title, description, default_knowledge_base_id,
                    default_pipeline_mode, default_knowledge_policy,
                    default_duration_seconds, default_style, default_enable_dubbing,
                    default_voice_mode, default_voice_profile_id, default_tts_speed,
                    default_keep_original_audio, created_at, updated_at
                ) VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    COALESCE((SELECT created_at FROM projects WHERE id = ?), ?),
                    ?
                )
                """,
                (
                    str(project.get("id", "") or "default"),
                    str(project.get("user_id", "") or "local"),
                    str(project.get("title", "") or "默认项目"),
                    str(project.get("description", "") or ""),
                    str(project.get("default_knowledge_base_id", "") or "default"),
                    str(project.get("default_pipeline_mode", "") or "narration_clip"),
                    str(project.get("default_knowledge_policy", "") or "none"),
                    int(project.get("default_duration_seconds", 0) or 0),
                    str(project.get("default_style", "") or "summary"),
                    1 if bool(project.get("default_enable_dubbing", False)) else 0,
                    str(project.get("default_voice_mode", "") or "standard"),
                    str(project.get("default_voice_profile_id", "") or ""),
                    float(project.get("default_tts_speed", 1.0) or 1.0),
                    1 if project.get("default_keep_original_audio", True) is not False else 0,
                    str(project.get("id", "") or "default"),
                    str(project.get("created_at", "") or project.get("updated_at", "")),
                    str(project.get("updated_at", "") or project.get("created_at", "")),
                ),
            )
            conn.commit()
        return self.get(
            str(project.get("id", "") or "default"),
            user_id=str(project.get("user_id", "") or "local"),
        )

    def delete(self, project_id: str, *, user_id: str = "local") -> bool:
        normalized_id = str(project_id or "").strip()
        normalized_user_id = str(user_id or "local").strip() or "local"
        if not normalized_id:
            return False
        with self._db._lock, self._db._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM projects WHERE id = ? AND user_id = ?",
                (normalized_id, normalized_user_id),
            )
            conn.commit()
        return bool(cursor.rowcount)
