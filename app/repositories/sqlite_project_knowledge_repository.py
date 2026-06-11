from __future__ import annotations

from typing import Any, Dict, List

from app.repositories.row_mappers import row_to_project_knowledge


class SQLiteProjectKnowledgeRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def get(self, knowledge_id: str = "default", *, user_id: str = "local") -> Dict[str, Any]:
        normalized_id = str(knowledge_id or "default").strip() or "default"
        normalized_user_id = str(user_id or "local").strip() or "local"
        with self._db._lock, self._db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM project_knowledge WHERE id = ? AND user_id = ?",
                (normalized_id, normalized_user_id),
            ).fetchone()
        if row is None:
            item = row_to_project_knowledge(None)
            item["id"] = normalized_id
            item["user_id"] = normalized_user_id
            return item
        return row_to_project_knowledge(row)

    def list(self, project_id: str = "", *, user_id: str = "local") -> List[Dict[str, Any]]:
        normalized_project_id = str(project_id or "").strip()
        normalized_user_id = str(user_id or "local").strip() or "local"
        with self._db._lock, self._db._connect() as conn:
            if normalized_project_id:
                rows = conn.execute(
                    """
                    SELECT * FROM project_knowledge
                    WHERE project_id = ? AND user_id = ?
                    ORDER BY updated_at DESC, title ASC
                    """,
                    (normalized_project_id, normalized_user_id),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM project_knowledge
                    WHERE user_id = ?
                    ORDER BY updated_at DESC, title ASC
                    """,
                    (normalized_user_id,),
                ).fetchall()
        items = [row_to_project_knowledge(row) for row in rows]
        if normalized_project_id:
            return items
        return items or [row_to_project_knowledge(None)]

    def upsert(
        self,
        *,
        title: str,
        content: str,
        now_iso: str,
        knowledge_id: str = "default",
        project_id: str = "default",
        user_id: str = "local",
    ) -> Dict[str, Any]:
        normalized_id = str(knowledge_id or "default").strip() or "default"
        normalized_project_id = str(project_id or "default").strip() or "default"
        normalized_user_id = str(user_id or "local").strip() or "local"
        normalized_title = str(title or "").strip() or "项目知识库"
        normalized_content = str(content or "").strip()
        with self._db._lock, self._db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO project_knowledge (
                    id, user_id, project_id, title, content, created_at, updated_at
                ) VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    COALESCE((SELECT created_at FROM project_knowledge WHERE id = ? AND user_id = ?), ?),
                    ?
                )
                """,
                (
                    normalized_id,
                    normalized_user_id,
                    normalized_project_id,
                    normalized_title,
                    normalized_content,
                    normalized_id,
                    normalized_user_id,
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()
        return self.get(normalized_id, user_id=normalized_user_id)

    def delete(self, knowledge_id: str, *, user_id: str = "local") -> bool:
        normalized_id = str(knowledge_id or "").strip()
        normalized_user_id = str(user_id or "local").strip() or "local"
        if not normalized_id:
            return False
        with self._db._lock, self._db._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM project_knowledge WHERE id = ? AND user_id = ?",
                (normalized_id, normalized_user_id),
            )
            conn.commit()
        return bool(cursor.rowcount)
