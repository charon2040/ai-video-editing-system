from typing import Any, Dict, List

from app.db.database import get_db_connection


class StudioTimelineTrackOps:
    def __init__(self, studio_service):
        self._studio = studio_service

    def clear_timeline_clips(self, project_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            self._studio._ensure_timeline_history_baseline(cursor, project_id, timeline["id"])
            cursor.execute("DELETE FROM timeline_clips WHERE timeline_id = ?", (timeline["id"],))
            self._studio._touch_project_timeline(cursor, project_id, timeline["id"])
            self._studio._push_timeline_history(cursor, project_id, timeline["id"], "clear_timeline_clips")
        return self._studio.get_project_timeline(project_id)

    def create_timeline_track(self, project_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            self._studio._ensure_timeline_history_baseline(cursor, project_id, timeline["id"])
            track_type = payload.get("track_type", "video")
            next_index = cursor.execute(
                """
                SELECT COALESCE(MAX(track_index), -1) + 1
                FROM timeline_tracks
                WHERE timeline_id = ? AND track_type = ?
                """,
                (timeline["id"], track_type),
            ).fetchone()[0]
            next_sort = cursor.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM timeline_tracks WHERE timeline_id = ?",
                (timeline["id"],),
            ).fetchone()[0]
            cursor.execute(
                """
                INSERT INTO timeline_tracks (
                    timeline_id, track_type, track_index, name, is_locked, is_muted, is_visible, sort_order
                )
                VALUES (?, ?, ?, ?, 0, 0, 1, ?)
                """,
                (
                    timeline["id"],
                    track_type,
                    next_index,
                    payload.get("name") or f"{str(track_type).upper()} Track {next_index}",
                    next_sort,
                ),
            )
            track_id = cursor.lastrowid
            self._studio._touch_project_timeline(cursor, project_id, timeline["id"])
            self._studio._push_timeline_history(cursor, project_id, timeline["id"], "create_track")
            row = cursor.execute("SELECT * FROM timeline_tracks WHERE id = ?", (track_id,)).fetchone()
        return self._studio._serialize_track(row)

    def delete_timeline_track(self, project_id: int, track_id: int) -> bool:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT tt.*
                FROM timeline_tracks tt
                JOIN timelines t ON t.id = tt.timeline_id
                WHERE tt.id = ? AND t.project_id = ?
                """,
                (track_id, project_id),
            ).fetchone()
            if row is None:
                return False
            clip_count = cursor.execute(
                """
                SELECT COUNT(*)
                FROM timeline_clips
                WHERE timeline_id = ? AND track_type = ? AND track_index = ?
                """,
                (row["timeline_id"], row["track_type"], row["track_index"]),
            ).fetchone()[0]
            if clip_count > 0:
                return False
            self._studio._ensure_timeline_history_baseline(cursor, project_id, row["timeline_id"])
            cursor.execute("DELETE FROM timeline_tracks WHERE id = ?", (track_id,))
            self._studio._touch_project_timeline(cursor, project_id, row["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, row["timeline_id"], "delete_track")
        return True

    def update_timeline_track(self, project_id: int, track_id: int, payload: Dict) -> Dict:
        allowed = {"name", "is_locked", "is_muted", "is_visible"}
        keys = [key for key in payload.keys() if key in allowed]
        if not keys:
            return {}
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT tt.*
                FROM timeline_tracks tt
                JOIN timelines t ON t.id = tt.timeline_id
                WHERE tt.id = ? AND t.project_id = ?
                """,
                (track_id, project_id),
            ).fetchone()
            if row is None:
                return {}
            self._studio._ensure_timeline_history_baseline(cursor, project_id, row["timeline_id"])

            update_fields = []
            values: List[Any] = []
            if "name" in payload:
                update_fields.append("name = ?")
                values.append(str(payload.get("name") or "").strip())
            if "is_locked" in payload:
                update_fields.append("is_locked = ?")
                values.append(1 if payload.get("is_locked") else 0)
            if "is_muted" in payload:
                update_fields.append("is_muted = ?")
                values.append(1 if payload.get("is_muted") else 0)
            if "is_visible" in payload:
                update_fields.append("is_visible = ?")
                values.append(1 if payload.get("is_visible") else 0)
            if not update_fields:
                return self._studio._serialize_track(row)
            values.append(track_id)
            cursor.execute(
                f"UPDATE timeline_tracks SET {', '.join(update_fields)} WHERE id = ?",
                tuple(values),
            )
            self._studio._touch_project_timeline(cursor, project_id, row["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, row["timeline_id"], "update_track")
            updated = cursor.execute("SELECT * FROM timeline_tracks WHERE id = ?", (track_id,)).fetchone()
        return self._studio._serialize_track(updated)

    def reorder_timeline_tracks(self, project_id: int, payload: Dict) -> Dict:
        track_ids = payload.get("track_ids", [])
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            self._studio._ensure_timeline_history_baseline(cursor, project_id, timeline["id"])

            rows = cursor.execute(
                """
                SELECT id
                FROM timeline_tracks
                WHERE timeline_id = ?
                ORDER BY sort_order ASC, id ASC
                """,
                (timeline["id"],),
            ).fetchall()
            existing_ids = [row["id"] for row in rows]
            valid_ids = [int(track_id) for track_id in track_ids if int(track_id) in existing_ids]
            final_ids = valid_ids + [track_id for track_id in existing_ids if track_id not in valid_ids]

            for sort_order, track_id in enumerate(final_ids):
                cursor.execute(
                    "UPDATE timeline_tracks SET sort_order = ? WHERE id = ?",
                    (sort_order, track_id),
                )
            self._studio._touch_project_timeline(cursor, project_id, timeline["id"])
            self._studio._push_timeline_history(cursor, project_id, timeline["id"], "reorder_tracks")
        return self._studio.get_project_timeline(project_id)
