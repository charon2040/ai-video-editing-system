from __future__ import annotations

import json
from typing import Any, Dict, List

from app.repositories.row_mappers import row_to_clip_plan


class SQLiteClipPlanRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def upsert(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        with self._db._lock, self._db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO clip_plans (
                    id, user_id, task_id, source_hash, request_text, request_mode,
                    duration_seconds, style, script, suggestions_json,
                    segments_json, plan_mode, total_duration_ms,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(plan.get("id", "")),
                    str(plan.get("user_id", "") or "local"),
                    str(plan.get("task_id", "")),
                    str(plan.get("source_hash", "")),
                    str(plan.get("request_text", "")),
                    str(plan.get("request_mode", "")),
                    int(plan.get("duration_seconds", 0) or 0),
                    str(plan.get("style", "")),
                    str(plan.get("script", "")),
                    json.dumps(plan.get("suggestions", []), ensure_ascii=False),
                    json.dumps(plan.get("segments", []), ensure_ascii=False),
                    str(plan.get("plan_mode", "")),
                    int(plan.get("total_duration_ms", 0) or 0),
                    str(plan.get("created_at", "")),
                    str(plan.get("updated_at", "")),
                ),
            )
            conn.commit()
        return plan

    def list(
        self,
        *,
        task_id: str | None = None,
        source_hash: str | None = None,
        user_id: str = "",
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM clip_plans"
        params: List[str] = []
        clauses: List[str] = []
        if user_id:
            clauses.append("user_id = ?")
            params.append(str(user_id))
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if source_hash:
            clauses.append("source_hash = ?")
            params.append(source_hash)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC"

        with self._db._lock, self._db._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [row_to_clip_plan(row) for row in rows]
