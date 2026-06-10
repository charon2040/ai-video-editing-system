import json
from typing import Any, Dict

from app.db.database import get_db_connection

def _json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class StudioHistoryOps:
    def __init__(self, studio_service):
        self._studio = studio_service

    def build_timeline_history_snapshot(self, cursor, timeline_id: int) -> Dict[str, Any]:
        timeline = cursor.execute("SELECT * FROM timelines WHERE id = ?", (timeline_id,)).fetchone()
        if timeline is None:
            return {}
        clips = cursor.execute(
            "SELECT * FROM timeline_clips WHERE timeline_id = ? ORDER BY sort_order ASC, id ASC",
            (timeline_id,),
        ).fetchall()
        tracks = cursor.execute(
            "SELECT * FROM timeline_tracks WHERE timeline_id = ? ORDER BY sort_order ASC, id ASC",
            (timeline_id,),
        ).fetchall()
        timeline_dict = dict(timeline)
        timeline_dict.pop("current_history_id", None)
        return {
            "timeline": timeline_dict,
            "clips": [dict(row) for row in clips],
            "tracks": [dict(row) for row in tracks],
        }

    def push_timeline_history(self, cursor, project_id: int, timeline_id: int, action: str):
        timeline = cursor.execute("SELECT id, current_history_id FROM timelines WHERE id = ?", (timeline_id,)).fetchone()
        if timeline is None:
            return
        current_history_id = timeline["current_history_id"]
        if current_history_id:
            cursor.execute(
                "DELETE FROM timeline_histories WHERE timeline_id = ? AND id > ?",
                (timeline_id, current_history_id),
            )
        snapshot = self.build_timeline_history_snapshot(cursor, timeline_id)
        cursor.execute(
            """
            INSERT INTO timeline_histories (project_id, timeline_id, action, snapshot_json)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, timeline_id, action, json.dumps(snapshot, ensure_ascii=False)),
        )
        history_id = cursor.lastrowid
        cursor.execute(
            "UPDATE timelines SET current_history_id = ? WHERE id = ?",
            (history_id, timeline_id),
        )

    def ensure_timeline_history_baseline(self, cursor, project_id: int, timeline_id: int):
        timeline = cursor.execute("SELECT current_history_id FROM timelines WHERE id = ?", (timeline_id,)).fetchone()
        if timeline is None:
            return
        if timeline["current_history_id"] is None:
            self.push_timeline_history(cursor, project_id, timeline_id, "init")

    def restore_timeline_history_row(self, cursor, project_id: int, timeline_id: int, history_row) -> bool:
        if history_row is None:
            return False
        snapshot = _json_loads(history_row["snapshot_json"], {})
        timeline_data = snapshot.get("timeline") or {}
        clips = snapshot.get("clips") or []
        tracks = snapshot.get("tracks") or []
        if not timeline_data:
            return False

        cursor.execute(
            """
            UPDATE timelines
            SET name = ?, resolution = ?, fps = ?, script = ?, status = ?,
                source_video_path = ?, source_edl_path = ?, render_blueprint_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND project_id = ?
            """,
            (
                timeline_data.get("name", "主时间线"),
                timeline_data.get("resolution", "1920x1080"),
                timeline_data.get("fps", 30),
                timeline_data.get("script", ""),
                timeline_data.get("status", "draft"),
                timeline_data.get("source_video_path", ""),
                timeline_data.get("source_edl_path", ""),
                timeline_data.get("render_blueprint_json", "{}"),
                timeline_id,
                project_id,
            ),
        )
        cursor.execute("DELETE FROM timeline_clips WHERE timeline_id = ?", (timeline_id,))
        cursor.execute("DELETE FROM timeline_tracks WHERE timeline_id = ?", (timeline_id,))

        for track in tracks:
            cursor.execute(
                """
                INSERT INTO timeline_tracks (
                    id, timeline_id, track_type, track_index, name, is_locked, is_muted, is_visible, sort_order, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    track.get("id"),
                    timeline_id,
                    track.get("track_type", "video"),
                    track.get("track_index", 0),
                    track.get("name", ""),
                    track.get("is_locked", 0),
                    track.get("is_muted", 0),
                    track.get("is_visible", 1),
                    track.get("sort_order", 0),
                    track.get("created_at"),
                ),
            )
        for clip in clips:
            cursor.execute(
                """
                INSERT INTO timeline_clips (
                    id, timeline_id, asset_id, clip_type, label, track_type, track_index, start_ms, end_ms,
                    source_start_ms, source_end_ms, content, dubbing, effects_json, transform_json, mask_json,
                    transition_json, metadata_json, sort_order, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clip.get("id"),
                    timeline_id,
                    clip.get("asset_id"),
                    clip.get("clip_type", "video"),
                    clip.get("label", ""),
                    clip.get("track_type", "video"),
                    clip.get("track_index", 0),
                    clip.get("start_ms", 0),
                    clip.get("end_ms", 0),
                    clip.get("source_start_ms", 0),
                    clip.get("source_end_ms", 0),
                    clip.get("content", ""),
                    clip.get("dubbing", ""),
                    clip.get("effects_json", "{}"),
                    clip.get("transform_json", "{}"),
                    clip.get("mask_json", "{}"),
                    clip.get("transition_json", "{}"),
                    clip.get("metadata_json", "{}"),
                    clip.get("sort_order", 0),
                    clip.get("created_at"),
                ),
            )
        cursor.execute(
            "UPDATE timelines SET current_history_id = ? WHERE id = ?",
            (history_row["id"], timeline_id),
        )
        self._studio._touch_project_timeline(cursor, project_id, timeline_id)
        return True

    def get_timeline_history_state(self, project_id: int) -> Dict[str, Any]:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {"can_undo": False, "can_redo": False, "current_history_id": None, "history_count": 0}
            current_id = timeline["current_history_id"]
            history_count = cursor.execute(
                "SELECT COUNT(*) FROM timeline_histories WHERE timeline_id = ?",
                (timeline["id"],),
            ).fetchone()[0]
            if not current_id:
                return {"can_undo": False, "can_redo": False, "current_history_id": None, "history_count": history_count}
            can_undo = cursor.execute(
                "SELECT 1 FROM timeline_histories WHERE timeline_id = ? AND id < ? LIMIT 1",
                (timeline["id"], current_id),
            ).fetchone() is not None
            can_redo = cursor.execute(
                "SELECT 1 FROM timeline_histories WHERE timeline_id = ? AND id > ? LIMIT 1",
                (timeline["id"], current_id),
            ).fetchone() is not None
        return {
            "can_undo": can_undo,
            "can_redo": can_redo,
            "current_history_id": current_id,
            "history_count": history_count,
        }

    def undo_timeline(self, project_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            self.ensure_timeline_history_baseline(cursor, project_id, timeline["id"])
            current_id = cursor.execute(
                "SELECT current_history_id FROM timelines WHERE id = ?",
                (timeline["id"],),
            ).fetchone()["current_history_id"]
            if current_id is None:
                return self._studio.get_project_timeline(project_id)
            prev_row = cursor.execute(
                """
                SELECT * FROM timeline_histories
                WHERE timeline_id = ? AND id < ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (timeline["id"], current_id),
            ).fetchone()
            if prev_row is None:
                return self._studio.get_project_timeline(project_id)
            self.restore_timeline_history_row(cursor, project_id, timeline["id"], prev_row)
        return self._studio.get_project_timeline(project_id)

    def redo_timeline(self, project_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            current_id = timeline["current_history_id"]
            if current_id is None:
                return self._studio.get_project_timeline(project_id)
            next_row = cursor.execute(
                """
                SELECT * FROM timeline_histories
                WHERE timeline_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (timeline["id"], current_id),
            ).fetchone()
            if next_row is None:
                return self._studio.get_project_timeline(project_id)
            self.restore_timeline_history_row(cursor, project_id, timeline["id"], next_row)
        return self._studio.get_project_timeline(project_id)

    def recover_timeline_history(self, project_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            self.ensure_timeline_history_baseline(cursor, project_id, timeline["id"])
            first_row = cursor.execute(
                """
                SELECT * FROM timeline_histories
                WHERE timeline_id = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (timeline["id"],),
            ).fetchone()
            if first_row is None:
                return self._studio.get_project_timeline(project_id)
            self.restore_timeline_history_row(cursor, project_id, timeline["id"], first_row)
        return self._studio.get_project_timeline(project_id)
