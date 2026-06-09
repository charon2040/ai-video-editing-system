from __future__ import annotations

import json
from typing import Any, Dict, List

from app.repositories.row_mappers import row_to_asr_cache


class SQLiteASRCacheRepository:
    def __init__(self, database: Any) -> None:
        self._db = database

    def get(self, source_hash: str) -> Dict[str, Any]:
        if not source_hash:
            return {}
        with self._db._lock, self._db._connect() as conn:
            row = conn.execute(
                "SELECT * FROM asr_cache WHERE source_hash = ?",
                (source_hash,),
            ).fetchone()
        return row_to_asr_cache(row)

    def upsert(
        self,
        *,
        source_hash: str,
        original_filename: str,
        source_size: int,
        audio_path: str,
        subtitles: List[Dict[str, Any]],
        now_iso: str,
    ) -> None:
        with self._db._lock, self._db._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO asr_cache (
                    source_hash, original_filename, source_size,
                    audio_path, subtitles_json, subtitle_count,
                    created_at, updated_at
                ) VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    COALESCE((SELECT created_at FROM asr_cache WHERE source_hash = ?), ?),
                    ?
                )
                """,
                (
                    source_hash,
                    original_filename,
                    int(source_size or 0),
                    audio_path,
                    json.dumps(subtitles, ensure_ascii=False),
                    len(subtitles),
                    source_hash,
                    now_iso,
                    now_iso,
                ),
            )
            conn.commit()

    def delete(self, source_hash: str) -> bool:
        normalized_hash = str(source_hash or "").strip()
        if not normalized_hash:
            return False
        with self._db._lock, self._db._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM asr_cache WHERE source_hash = ?",
                (normalized_hash,),
            )
            conn.commit()
        return int(cursor.rowcount or 0) > 0
