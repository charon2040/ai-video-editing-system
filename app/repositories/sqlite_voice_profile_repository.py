from __future__ import annotations

from typing import Any, Dict, List

from app.repositories.row_mappers import row_to_voice_profile


class SQLiteVoiceProfileRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def upsert(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        with self._db._lock, self._db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO voice_profiles (
                    id, user_id, label, description, prompt_text, prompt_wav_path,
                    language, source_type, is_default, is_active, sort_order,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(profile.get("id", "")),
                    "" if str(profile.get("source_type", "seed") or "seed") == "seed" else str(profile.get("user_id", "") or "local"),
                    str(profile.get("label", "")),
                    str(profile.get("description", "")),
                    str(profile.get("prompt_text", "")),
                    str(profile.get("prompt_wav_path", "")),
                    str(profile.get("language", "")),
                    str(profile.get("source_type", "seed") or "seed"),
                    1 if profile.get("is_default") else 0,
                    0 if profile.get("is_active") is False else 1,
                    int(profile.get("sort_order", 0) or 0),
                    str(profile.get("created_at", "")),
                    str(profile.get("updated_at", "")),
                ),
            )
            conn.commit()
        return profile

    def get(self, profile_id: str, *, user_id: str = "") -> Dict[str, Any]:
        if not profile_id:
            return {}
        normalized_user_id = str(user_id or "").strip()
        with self._db._lock, self._db._connect() as conn:
            if normalized_user_id:
                row = conn.execute(
                    """
                    SELECT * FROM voice_profiles
                    WHERE id = ? AND (user_id = '' OR user_id = ?)
                    ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END
                    LIMIT 1
                    """,
                    (profile_id, normalized_user_id, normalized_user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM voice_profiles WHERE id = ?",
                    (profile_id,),
                ).fetchone()
        return row_to_voice_profile(row)

    def find_by_label(self, label: str, *, user_id: str = "") -> Dict[str, Any]:
        normalized = str(label or "").strip()
        if not normalized:
            return {}
        normalized_user_id = str(user_id or "").strip()
        with self._db._lock, self._db._connect() as conn:
            if normalized_user_id:
                row = conn.execute(
                    """
                    SELECT * FROM voice_profiles
                    WHERE label = ? AND (user_id = '' OR user_id = ?)
                    ORDER BY CASE WHEN user_id = ? THEN 0 ELSE 1 END,
                             is_active DESC, is_default DESC, sort_order ASC
                    LIMIT 1
                    """,
                    (normalized, normalized_user_id, normalized_user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM voice_profiles WHERE label = ? ORDER BY is_active DESC, is_default DESC, sort_order ASC LIMIT 1",
                    (normalized,),
                ).fetchone()
        return row_to_voice_profile(row)

    def list(self, *, active_only: bool = False, user_id: str = "") -> List[Dict[str, Any]]:
        normalized_user_id = str(user_id or "").strip()
        clauses: List[str] = []
        params: List[str] = []
        if active_only:
            clauses.append("is_active = 1")
        if normalized_user_id:
            clauses.append("(user_id = '' OR user_id = ?)")
            params.append(normalized_user_id)

        sql = "SELECT * FROM voice_profiles"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY is_default DESC, sort_order ASC, label ASC"
        with self._db._lock, self._db._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [row_to_voice_profile(row) for row in rows]
