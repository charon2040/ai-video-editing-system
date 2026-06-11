from __future__ import annotations

from typing import Any, Dict

from app.repositories.row_mappers import row_to_user, row_to_user_session


class SQLiteUserRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def upsert(self, user: Dict[str, Any]) -> Dict[str, Any]:
        with self._db._lock, self._db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO users (
                    id, username, password_hash, display_name, is_active,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(user.get("id", "")),
                    str(user.get("username", "")),
                    str(user.get("password_hash", "")),
                    str(user.get("display_name", "")),
                    0 if user.get("is_active") is False else 1,
                    str(user.get("created_at", "")),
                    str(user.get("updated_at", "")),
                ),
            )
            conn.commit()
        return self.get(str(user.get("id", "")))

    def get(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            return {}
        with self._db._lock, self._db._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (str(user_id),)).fetchone()
        return row_to_user(row)

    def find_by_username(self, username: str) -> Dict[str, Any]:
        normalized = str(username or "").strip().lower()
        if not normalized:
            return {}
        with self._db._lock, self._db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE lower(username) = ?",
                (normalized,),
            ).fetchone()
        return row_to_user(row)


class SQLiteUserSessionRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def upsert(self, session: Dict[str, Any]) -> Dict[str, Any]:
        with self._db._lock, self._db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO user_sessions (
                    token_hash, user_id, created_at, expires_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(session.get("token_hash", "")),
                    str(session.get("user_id", "")),
                    str(session.get("created_at", "")),
                    str(session.get("expires_at", "")),
                    str(session.get("last_seen_at", "")),
                ),
            )
            conn.commit()
        return self.get(str(session.get("token_hash", "")))

    def get(self, token_hash: str) -> Dict[str, Any]:
        if not token_hash:
            return {}
        with self._db._lock, self._db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM user_sessions WHERE token_hash = ?",
                (str(token_hash),),
            ).fetchone()
        return row_to_user_session(row)

    def delete(self, token_hash: str) -> bool:
        if not token_hash:
            return False
        with self._db._lock, self._db._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM user_sessions WHERE token_hash = ?",
                (str(token_hash),),
            )
            conn.commit()
        return int(cursor.rowcount or 0) > 0

    def delete_expired(self, now_iso: str) -> int:
        with self._db._lock, self._db._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM user_sessions WHERE expires_at <= ?",
                (str(now_iso),),
            )
            conn.commit()
        return int(cursor.rowcount or 0)
