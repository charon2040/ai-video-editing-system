import json
from typing import Dict

from app.db.database import get_db_connection


class StudioTimelineCoreOps:
    def __init__(self, studio_service):
        self._studio = studio_service

    def get_timeline_by_id(self, timeline_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = cursor.execute("SELECT * FROM timelines WHERE id = ?", (timeline_id,)).fetchone()
            if timeline is None:
                return {}
            track_rows = self._studio._get_track_rows(cursor, timeline_id)
            clip_rows = cursor.execute(
                "SELECT * FROM timeline_clips WHERE timeline_id = ? ORDER BY sort_order ASC, id ASC",
                (timeline_id,),
            ).fetchall()
        return self._studio._serialize_timeline(timeline, [self._studio._serialize_clip(row) for row in clip_rows], track_rows)

    def upsert_timeline(self, project_id: int, payload: Dict) -> Dict:
        source_video_path = self._studio._resolve_storage_path(payload.get("source_video_path", ""))
        source_edl_path = self._studio._resolve_storage_path(payload.get("source_edl_path", ""))
        render_blueprint_json = json.dumps(payload.get("render_blueprint", {}), ensure_ascii=False)
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = cursor.execute("SELECT * FROM timelines WHERE project_id = ?", (project_id,)).fetchone()
            if timeline is None:
                cursor.execute(
                    """
                    INSERT INTO timelines (
                        project_id, name, resolution, fps, script, status,
                        source_video_path, source_edl_path, render_blueprint_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        project_id,
                        payload.get("name", "主时间线"),
                        payload.get("resolution", "1920x1080"),
                        payload.get("fps", 30),
                        payload.get("script", ""),
                        payload.get("status", "draft"),
                        source_video_path,
                        source_edl_path,
                        render_blueprint_json,
                    ),
                )
                timeline_id = cursor.lastrowid
                self._studio._ensure_default_tracks(cursor, timeline_id)
            else:
                timeline_id = timeline["id"]
                self._studio._ensure_timeline_history_baseline(cursor, project_id, timeline_id)
                self._studio._ensure_default_tracks(cursor, timeline_id)
                cursor.execute(
                    """
                    UPDATE timelines
                    SET name = ?, resolution = ?, fps = ?, script = ?, status = ?,
                        source_video_path = ?, source_edl_path = ?, render_blueprint_json = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        payload.get("name", timeline["name"]),
                        payload.get("resolution", timeline["resolution"]),
                        payload.get("fps", timeline["fps"]),
                        payload.get("script", timeline["script"]),
                        payload.get("status", timeline["status"]),
                        source_video_path or timeline["source_video_path"],
                        source_edl_path or timeline["source_edl_path"],
                        render_blueprint_json,
                        timeline_id,
                    ),
                )

            cursor.execute("DELETE FROM timeline_clips WHERE timeline_id = ?", (timeline_id,))
            for index, clip in enumerate(payload.get("clips", [])):
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO timeline_tracks (
                        timeline_id, track_type, track_index, name, is_locked, is_muted, is_visible, sort_order
                    )
                    VALUES (?, ?, ?, ?, 0, 0, 1,
                        COALESCE((SELECT MAX(sort_order) + 1 FROM timeline_tracks WHERE timeline_id = ?), 0)
                    )
                    """,
                    (
                        timeline_id,
                        clip.get("track_type", "video"),
                        clip.get("track_index", 0),
                        f'{str(clip.get("track_type", "video")).upper()} Track {clip.get("track_index", 0)}',
                        timeline_id,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO timeline_clips (
                        timeline_id, asset_id, clip_type, label, track_type, track_index, start_ms, end_ms,
                        source_start_ms, source_end_ms, content, dubbing, effects_json,
                        transform_json, mask_json, transition_json, metadata_json, sort_order
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
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
                        json.dumps(clip.get("effects", {}), ensure_ascii=False),
                        json.dumps(clip.get("transform", {}), ensure_ascii=False),
                        "{}",
                        json.dumps(clip.get("transition", {}), ensure_ascii=False),
                        json.dumps(clip.get("metadata", {}), ensure_ascii=False),
                        clip.get("sort_order", index),
                    ),
                )

            cursor.execute(
                "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (project_id,),
            )
            self._studio._push_timeline_history(cursor, project_id, timeline_id, "upsert_timeline")
        return self._studio.get_project_timeline(project_id)

    def update_timeline_clip(self, project_id: int, clip_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT c.*, t.project_id
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (clip_id, project_id),
            ).fetchone()
            if row is None:
                return {}

            current = self._studio._serialize_clip(row)
            self._studio._ensure_timeline_history_baseline(cursor, project_id, current["timeline_id"])
            updated_clip_type = payload.get("clip_type", current.get("clip_type", "video"))
            updated_track_type = payload.get("track_type", current.get("track_type", "video"))
            updated_track_index = payload.get("track_index", current.get("track_index", 0))
            source_track_type = current.get("track_type", "video")
            source_track_index = int(current.get("track_index", 0) or 0)
            if self._studio._is_track_locked(cursor, current["timeline_id"], source_track_type, source_track_index):
                return {}
            updated_start_ms = payload.get("start_ms", current.get("start_ms", 0))
            updated_end_ms = payload.get("end_ms", current.get("end_ms", 0))
            updated_source_start_ms = payload.get("source_start_ms", current.get("source_start_ms", 0))
            updated_source_end_ms = payload.get("source_end_ms", current.get("source_end_ms", 0))
            updated_label = payload.get("label", current.get("label", ""))
            updated_content = payload.get("content", current.get("content", ""))
            updated_dubbing = payload.get("dubbing", current.get("dubbing", ""))
            updated_effects = payload.get("effects", current.get("effects", {}))
            updated_transform = payload.get("transform", current.get("transform", {}))
            updated_transition = payload.get("transition", current.get("transition", {}))
            updated_metadata = payload.get("metadata", current.get("metadata", {}))
            cursor.execute(
                """
                INSERT OR IGNORE INTO timeline_tracks (
                    timeline_id, track_type, track_index, name, is_locked, is_muted, is_visible, sort_order
                )
                VALUES (?, ?, ?, ?, 0, 0, 1,
                    COALESCE((SELECT MAX(sort_order) + 1 FROM timeline_tracks WHERE timeline_id = ?), 0)
                )
                """,
                (
                    current["timeline_id"],
                    updated_track_type,
                    updated_track_index,
                    f"{str(updated_track_type).upper()} Track {updated_track_index}",
                    current["timeline_id"],
                ),
            )
            if self._studio._is_track_locked(cursor, current["timeline_id"], updated_track_type, int(updated_track_index or 0)):
                return {}
            if any(key in payload for key in ("track_type", "track_index", "start_ms", "end_ms")):
                updated_start_ms, updated_end_ms = self._studio._constrain_clip_interval(
                    cursor=cursor,
                    timeline_id=current["timeline_id"],
                    track_type=updated_track_type,
                    track_index=int(updated_track_index or 0),
                    start_ms=int(updated_start_ms or 0),
                    end_ms=int(updated_end_ms or 0),
                    exclude_clip_id=int(clip_id),
                )

            cursor.execute(
                """
                UPDATE timeline_clips
                SET clip_type = ?, track_type = ?, track_index = ?, start_ms = ?, end_ms = ?,
                    source_start_ms = ?, source_end_ms = ?, label = ?, content = ?, dubbing = ?,
                    effects_json = ?, transform_json = ?, mask_json = ?, transition_json = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    updated_clip_type,
                    updated_track_type,
                    updated_track_index,
                    updated_start_ms,
                    updated_end_ms,
                    updated_source_start_ms,
                    updated_source_end_ms,
                    updated_label,
                    updated_content,
                    updated_dubbing,
                    json.dumps(updated_effects, ensure_ascii=False),
                    json.dumps(updated_transform, ensure_ascii=False),
                    "{}",
                    json.dumps(updated_transition, ensure_ascii=False),
                    json.dumps(updated_metadata, ensure_ascii=False),
                    clip_id,
                ),
            )
            self._studio._touch_project_timeline(cursor, project_id, current["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, current["timeline_id"], "update_clip")
            updated_row = cursor.execute("SELECT * FROM timeline_clips WHERE id = ?", (clip_id,)).fetchone()
        return self._studio._serialize_clip(updated_row)

    def create_timeline_clip(self, project_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            self._studio._ensure_timeline_history_baseline(cursor, project_id, timeline["id"])
            if self._studio._is_track_locked(
                cursor,
                timeline["id"],
                payload.get("track_type", "video"),
                int(payload.get("track_index", 0) or 0),
            ):
                return {}

            next_sort_order = cursor.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM timeline_clips WHERE timeline_id = ?",
                (timeline["id"],),
            ).fetchone()[0]
            cursor.execute(
                """
                INSERT OR IGNORE INTO timeline_tracks (
                    timeline_id, track_type, track_index, name, is_locked, is_muted, is_visible, sort_order
                )
                VALUES (?, ?, ?, ?, 0, 0, 1,
                    COALESCE((SELECT MAX(sort_order) + 1 FROM timeline_tracks WHERE timeline_id = ?), 0)
                )
                """,
                (
                    timeline["id"],
                    payload.get("track_type", "video"),
                    payload.get("track_index", 0),
                    f'{str(payload.get("track_type", "video")).upper()} Track {payload.get("track_index", 0)}',
                    timeline["id"],
                ),
            )
            constrained_start_ms, constrained_end_ms = self._studio._constrain_clip_interval(
                cursor=cursor,
                timeline_id=timeline["id"],
                track_type=payload.get("track_type", "video"),
                track_index=int(payload.get("track_index", 0) or 0),
                start_ms=int(payload.get("start_ms", 0) or 0),
                end_ms=int(payload.get("end_ms", 0) or 0),
                exclude_clip_id=None,
            )
            cursor.execute(
                """
                INSERT INTO timeline_clips (
                    timeline_id, asset_id, clip_type, label, track_type, track_index, start_ms, end_ms,
                    source_start_ms, source_end_ms, content, dubbing, effects_json, transform_json,
                    mask_json, transition_json, metadata_json, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timeline["id"],
                    payload.get("asset_id"),
                    payload.get("clip_type", "video"),
                    payload.get("label", ""),
                    payload.get("track_type", "video"),
                    payload.get("track_index", 0),
                    constrained_start_ms,
                    constrained_end_ms,
                    payload.get("source_start_ms", 0),
                    payload.get("source_end_ms", 0),
                    payload.get("content", ""),
                    payload.get("dubbing", ""),
                    json.dumps(payload.get("effects", {}), ensure_ascii=False),
                    json.dumps(payload.get("transform", {}), ensure_ascii=False),
                    "{}",
                    json.dumps(payload.get("transition", {}), ensure_ascii=False),
                    json.dumps(payload.get("metadata", {}), ensure_ascii=False),
                    payload.get("sort_order", next_sort_order),
                ),
            )
            new_clip_id = cursor.lastrowid
            self._studio._touch_project_timeline(cursor, project_id, timeline["id"])
            self._studio._push_timeline_history(cursor, project_id, timeline["id"], "create_clip")
            created = cursor.execute("SELECT * FROM timeline_clips WHERE id = ?", (new_clip_id,)).fetchone()
        return self._studio._serialize_clip(created)

    def delete_timeline_clip(self, project_id: int, clip_id: int) -> bool:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT c.id, c.timeline_id, c.track_type, c.track_index
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (clip_id, project_id),
            ).fetchone()
            if row is None:
                return False
            if self._studio._is_track_locked(cursor, row["timeline_id"], row["track_type"], int(row["track_index"] or 0)):
                return False

            self._studio._ensure_timeline_history_baseline(cursor, project_id, row["timeline_id"])
            cursor.execute("DELETE FROM timeline_clips WHERE id = ?", (clip_id,))
            self._studio._touch_project_timeline(cursor, project_id, row["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, row["timeline_id"], "delete_clip")
        return True
