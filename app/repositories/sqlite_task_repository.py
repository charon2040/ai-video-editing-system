from __future__ import annotations

import json
from typing import Any, Dict, List

from app.repositories.row_mappers import row_to_task, row_to_task_event


class SQLiteTaskRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def list(self, *, user_id: str = "local") -> List[Dict[str, Any]]:
        normalized_user_id = str(user_id or "local").strip() or "local"
        with self._db._lock, self._db._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (normalized_user_id,),
            ).fetchall()
        return [row_to_task(row) for row in rows]

    def get(self, task_id: str, *, user_id: str = "") -> Dict[str, Any]:
        normalized_user_id = str(user_id or "").strip()
        with self._db._lock, self._db._connect() as conn:
            if normalized_user_id:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                    (task_id, normalized_user_id),
                ).fetchone()
            else:
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return row_to_task(row)

    def upsert(self, task: Dict[str, Any]) -> Dict[str, Any]:
        with self._db._lock, self._db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    id, user_id, project_id, status, progress, stage, message,
                    created_at, updated_at,
                    payload_json, artifacts_json, result_json,
                    error, source_path, source_hash, source_size
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(task.get("id", "")),
                    str(task.get("user_id", "") or task.get("payload", {}).get("user_id", "") or "local"),
                    str(task.get("project_id", "") or task.get("payload", {}).get("project_id", "") or "default"),
                    str(task.get("status", "queued")),
                    int(task.get("progress", 0) or 0),
                    str(task.get("stage", "queued")),
                    str(task.get("message", "")),
                    str(task.get("created_at", "")),
                    str(task.get("updated_at", "")),
                    json.dumps(task.get("payload", {}), ensure_ascii=False),
                    json.dumps(task.get("artifacts", {}), ensure_ascii=False),
                    json.dumps(task.get("result", {}), ensure_ascii=False),
                    str(task.get("error", "")),
                    str(task.get("source_path", "")),
                    str(task.get("source_hash", "")),
                    int(task.get("source_size", 0) or 0),
                ),
            )
            conn.commit()
        return task

    def delete(self, task_id: str, *, user_id: str = "") -> bool:
        if not task_id:
            return False
        normalized_user_id = str(user_id or "").strip()
        with self._db._lock, self._db._connect() as conn:
            if normalized_user_id:
                row = conn.execute(
                    "SELECT id FROM tasks WHERE id = ? AND user_id = ?",
                    (task_id, normalized_user_id),
                ).fetchone()
            else:
                row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return False
            conn.execute("DELETE FROM clip_plans WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        return True

    def count_by_source_hash(self, source_hash: str, *, exclude_task_id: str = "") -> int:
        normalized_hash = str(source_hash or "").strip()
        if not normalized_hash:
            return 0
        normalized_exclude = str(exclude_task_id or "").strip()
        with self._db._lock, self._db._connect() as conn:
            if normalized_exclude:
                row = conn.execute(
                    "SELECT COUNT(*) AS count FROM tasks WHERE source_hash = ? AND id != ?",
                    (normalized_hash, normalized_exclude),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS count FROM tasks WHERE source_hash = ?",
                    (normalized_hash,),
                ).fetchone()
        return int(row["count"] or 0) if row else 0

    def count_by_source_path(self, source_path: str, *, exclude_task_id: str = "") -> int:
        normalized_path = str(source_path or "").strip()
        if not normalized_path:
            return 0
        normalized_exclude = str(exclude_task_id or "").strip()
        with self._db._lock, self._db._connect() as conn:
            if normalized_exclude:
                row = conn.execute(
                    "SELECT COUNT(*) AS count FROM tasks WHERE source_path = ? AND id != ?",
                    (normalized_path, normalized_exclude),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) AS count FROM tasks WHERE source_path = ?",
                    (normalized_path,),
                ).fetchone()
        return int(row["count"] or 0) if row else 0

    def recover_interrupted(self, now_iso: str) -> int:
        with self._db._lock, self._db._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE status IN ('queued', 'running')"
            ).fetchall()

        recovered = 0
        for row in rows:
            task = row_to_task(row)
            task["status"] = "failed"
            task["stage"] = "failed"
            task["progress"] = 100
            task["message"] = "服务已重启，旧任务已中断，请重新提交"
            task["error"] = "任务在服务重启前未完成，已自动标记为失败。"
            task["updated_at"] = now_iso
            self.upsert(task)
            recovered += 1
        return recovered


class SQLiteTaskEventRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def insert(
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
        normalized_detail = detail or {}
        with self._db._lock, self._db._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO task_events (
                    task_id, event_type, status, stage, progress,
                    message, detail_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(task_id or ""),
                    str(event_type or "state_changed"),
                    str(status or ""),
                    str(stage or ""),
                    int(progress or 0),
                    str(message or ""),
                    json.dumps(normalized_detail, ensure_ascii=False),
                    str(created_at or ""),
                ),
            )
            event_id = int(cursor.lastrowid or 0)
            conn.commit()

        return {
            "id": event_id,
            "task_id": str(task_id or ""),
            "event_type": str(event_type or "state_changed"),
            "status": str(status or ""),
            "stage": str(stage or ""),
            "progress": int(progress or 0),
            "message": str(message or ""),
            "detail": normalized_detail,
            "created_at": str(created_at or ""),
        }

    def list(self, task_id: str, *, limit: int = 200) -> List[Dict[str, Any]]:
        if not task_id:
            return []
        safe_limit = max(1, min(500, int(limit or 200)))
        with self._db._lock, self._db._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_events
                WHERE task_id = ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (str(task_id), safe_limit),
            ).fetchall()
        return [row_to_task_event(row) for row in rows]
