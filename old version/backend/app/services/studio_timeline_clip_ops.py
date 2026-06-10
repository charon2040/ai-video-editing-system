import json
from typing import Dict

from app.db.database import get_db_connection


class StudioTimelineClipOps:
    def __init__(self, studio_service):
        self._studio = studio_service

    def separate_audio_from_timeline_clip(self, project_id: int, clip_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT c.*
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (clip_id, project_id),
            ).fetchone()
            if row is None:
                return {}

            clip = self._studio._serialize_clip(row)
            if clip.get("clip_type") != "video":
                return {}
            if self._studio._is_track_locked(cursor, clip["timeline_id"], clip.get("track_type", "video"), int(clip.get("track_index", 0) or 0)):
                return {}

            asset_id = int(clip.get("asset_id") or 0)
            if not asset_id:
                return {}

            asset_row = cursor.execute(
                "SELECT * FROM media_assets WHERE id = ? AND project_id = ?",
                (asset_id, project_id),
            ).fetchone()
            if asset_row is None:
                return {}

            self._studio._ensure_timeline_history_baseline(cursor, project_id, clip["timeline_id"])
            source_asset = dict(asset_row)
            audio_asset = self._studio._extract_audio_asset(cursor, project_id, source_asset)
            if not audio_asset:
                return {}
            silent_video_asset = self._studio._strip_audio_from_asset(cursor, project_id, source_asset)
            if not silent_video_asset:
                return {}

            next_audio_track_index = cursor.execute(
                """
                SELECT COALESCE(MAX(track_index), -1) + 1
                FROM timeline_tracks
                WHERE timeline_id = ? AND track_type = 'audio'
                """,
                (clip["timeline_id"],),
            ).fetchone()[0]
            next_audio_track_index = int(next_audio_track_index or 0)

            cursor.execute(
                """
                INSERT OR IGNORE INTO timeline_tracks (
                    timeline_id, track_type, track_index, name, is_locked, is_muted, is_visible, sort_order
                )
                VALUES (?, 'audio', ?, ?, 0, 0, 1,
                    COALESCE((SELECT MAX(sort_order) + 1 FROM timeline_tracks WHERE timeline_id = ?), 0)
                )
                """,
                (
                    clip["timeline_id"],
                    next_audio_track_index,
                    f"AUDIO Track {next_audio_track_index}",
                    clip["timeline_id"],
                ),
            )

            next_sort_order = cursor.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM timeline_clips WHERE timeline_id = ?",
                (clip["timeline_id"],),
            ).fetchone()[0]
            clip_duration_ms = max(0, int(clip.get("end_ms", 0) or 0) - int(clip.get("start_ms", 0) or 0))
            audio_metadata = {
                "source_path": audio_asset.get("file_path", ""),
                "audio": {
                    "volume": 1,
                },
                "generated_from_clip_id": clip_id,
                "generated_from_asset_id": asset_id,
            }
            cursor.execute(
                """
                INSERT INTO timeline_clips (
                    timeline_id, asset_id, clip_type, label, track_type, track_index, start_ms, end_ms,
                    source_start_ms, source_end_ms, content, dubbing, effects_json, transform_json,
                    mask_json, transition_json, metadata_json, sort_order
                ) VALUES (?, ?, 'audio', ?, 'audio', ?, ?, ?, ?, ?, '', '', '{}', '{}', '{}', '{}', ?, ?)
                """,
                (
                    clip["timeline_id"],
                    audio_asset.get("id"),
                    audio_asset.get("name", "Separated Audio"),
                    next_audio_track_index,
                    int(clip.get("start_ms", 0) or 0),
                    int(clip.get("end_ms", 0) or 0),
                    int(clip.get("source_start_ms", 0) or 0),
                    int(clip.get("source_start_ms", 0) or 0) + clip_duration_ms,
                    json.dumps(audio_metadata, ensure_ascii=False),
                    next_sort_order,
                ),
            )
            new_audio_clip_id = cursor.lastrowid

            metadata = clip.get("metadata", {}) or {}
            metadata["source_path"] = silent_video_asset.get("file_path", "") or metadata.get("source_path", "")
            metadata["video"] = {
                **(metadata.get("video", {}) or {}),
                "volume": 1,
            }
            metadata["separate_audio"] = {
                "audio_asset_id": audio_asset.get("id"),
                "silent_video_asset_id": silent_video_asset.get("id"),
                "generated_from_asset_id": asset_id,
            }
            cursor.execute(
                "UPDATE timeline_clips SET asset_id = ?, metadata_json = ? WHERE id = ?",
                (silent_video_asset.get("id"), json.dumps(metadata, ensure_ascii=False), clip_id),
            )

            self._studio._touch_project_timeline(cursor, project_id, clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, clip["timeline_id"], "separate_audio")
            created_row = cursor.execute("SELECT * FROM timeline_clips WHERE id = ?", (new_audio_clip_id,)).fetchone()

        return {
            "asset": audio_asset,
            "video_asset": silent_video_asset,
            "audio_clip": self._studio._serialize_clip(created_row),
            "timeline": self._studio.get_project_timeline(project_id),
        }

    def ripple_split_timeline_clip(self, project_id: int, clip_id: int, split_ms: int, keep: str = "right") -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT c.*
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (clip_id, project_id),
            ).fetchone()
            if row is None:
                return {}
            clip = self._studio._serialize_clip(row)
            if self._studio._is_track_locked(cursor, clip["timeline_id"], clip.get("track_type", "video"), int(clip.get("track_index", 0) or 0)):
                return {}
            clip_start = int(clip.get("start_ms", 0) or 0)
            clip_end = int(clip.get("end_ms", 0) or 0)
            split_at = int(split_ms or 0)
            if split_at <= clip_start or split_at >= clip_end:
                return {}
            mode = str(keep or "right").lower()
            if mode not in {"left", "right"}:
                return {}

            self._studio._ensure_timeline_history_baseline(cursor, project_id, clip["timeline_id"])
            split_offset = split_at - clip_start
            split_source_ms = int(clip.get("source_start_ms", 0) or 0) + split_offset
            shift_ms = 0
            if mode == "right":
                removed_ms = split_at - clip_start
                shift_ms = removed_ms
                cursor.execute(
                    """
                    UPDATE timeline_clips
                    SET start_ms = ?, end_ms = ?, source_start_ms = ?
                    WHERE id = ?
                    """,
                    (clip_start, clip_end - removed_ms, split_source_ms, clip_id),
                )
                cursor.execute(
                    """
                    UPDATE timeline_clips
                    SET start_ms = start_ms - ?, end_ms = end_ms - ?
                    WHERE timeline_id = ? AND track_type = ? AND track_index = ? AND id != ? AND start_ms >= ?
                    """,
                    (
                        removed_ms,
                        removed_ms,
                        clip["timeline_id"],
                        clip.get("track_type", "video"),
                        int(clip.get("track_index", 0) or 0),
                        clip_id,
                        clip_end,
                    ),
                )
            else:
                removed_ms = clip_end - split_at
                shift_ms = removed_ms
                cursor.execute(
                    """
                    UPDATE timeline_clips
                    SET end_ms = ?, source_end_ms = ?
                    WHERE id = ?
                    """,
                    (split_at, split_source_ms, clip_id),
                )
                cursor.execute(
                    """
                    UPDATE timeline_clips
                    SET start_ms = start_ms - ?, end_ms = end_ms - ?
                    WHERE timeline_id = ? AND track_type = ? AND track_index = ? AND start_ms >= ?
                    """,
                    (
                        removed_ms,
                        removed_ms,
                        clip["timeline_id"],
                        clip.get("track_type", "video"),
                        int(clip.get("track_index", 0) or 0),
                        clip_end,
                    ),
                )
            if shift_ms <= 0:
                return {}
            self._studio._touch_project_timeline(cursor, project_id, clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, clip["timeline_id"], f"ripple_split_{mode}")
        return self._studio.get_project_timeline(project_id)

    def split_timeline_clip(self, project_id: int, clip_id: int, split_ms: int, keep: str = "both") -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT c.*
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (clip_id, project_id),
            ).fetchone()
            if row is None:
                return {}
            clip = self._studio._serialize_clip(row)
            if self._studio._is_track_locked(cursor, clip["timeline_id"], clip.get("track_type", "video"), int(clip.get("track_index", 0) or 0)):
                return {}
            clip_start = int(clip.get("start_ms", 0) or 0)
            clip_end = int(clip.get("end_ms", 0) or 0)
            split_at = int(split_ms or 0)
            if split_at <= clip_start or split_at >= clip_end:
                return {}

            self._studio._ensure_timeline_history_baseline(cursor, project_id, clip["timeline_id"])
            split_offset = split_at - clip_start
            split_source_ms = int(clip.get("source_start_ms", 0) or 0) + split_offset
            mode = str(keep or "both").lower()

            if mode == "left":
                cursor.execute(
                    """
                    UPDATE timeline_clips
                    SET end_ms = ?, source_end_ms = ?, transition_json = '{}'
                    WHERE id = ?
                    """,
                    (split_at, split_source_ms, clip_id),
                )
            elif mode == "right":
                cursor.execute(
                    """
                    UPDATE timeline_clips
                    SET start_ms = ?, source_start_ms = ?, transition_json = '{}'
                    WHERE id = ?
                    """,
                    (split_at, split_source_ms, clip_id),
                )
            else:
                original_sort_order = int(clip.get("sort_order", 0) or 0)
                cursor.execute(
                    "UPDATE timeline_clips SET sort_order = sort_order + 1 WHERE timeline_id = ? AND sort_order > ?",
                    (clip["timeline_id"], original_sort_order),
                )
                cursor.execute(
                    """
                    UPDATE timeline_clips
                    SET end_ms = ?, source_end_ms = ?, transition_json = '{}'
                    WHERE id = ?
                    """,
                    (split_at, split_source_ms, clip_id),
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
                        clip["timeline_id"],
                        clip.get("asset_id"),
                        clip.get("clip_type", "video"),
                        clip.get("label", ""),
                        clip.get("track_type", "video"),
                        clip.get("track_index", 0),
                        split_at,
                        clip_end,
                        split_source_ms,
                        clip.get("source_end_ms", 0),
                        clip.get("content", ""),
                        clip.get("dubbing", ""),
                        json.dumps(clip.get("effects", {}), ensure_ascii=False),
                        json.dumps(clip.get("transform", {}), ensure_ascii=False),
                        "{}",
                        "{}",
                        json.dumps(clip.get("metadata", {}), ensure_ascii=False),
                        original_sort_order + 1,
                    ),
                )

            self._studio._touch_project_timeline(cursor, project_id, clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, clip["timeline_id"], f"split_clip_{mode}")
        return self._studio.get_project_timeline(project_id)

    def concat_timeline_clips(self, project_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            left_id = int(payload.get("left_clip_id") or 0)
            right_id = int(payload.get("right_clip_id") or 0)
            if not left_id or not right_id or left_id == right_id:
                return {}

            left_row = cursor.execute(
                """
                SELECT c.*
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (left_id, project_id),
            ).fetchone()
            right_row = cursor.execute(
                """
                SELECT c.*
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (right_id, project_id),
            ).fetchone()
            if left_row is None or right_row is None:
                return {}

            left_clip = self._studio._serialize_clip(left_row)
            right_clip = self._studio._serialize_clip(right_row)
            if left_clip.get("timeline_id") != right_clip.get("timeline_id"):
                return {}
            if left_clip.get("track_type") != right_clip.get("track_type"):
                return {}
            if left_clip.get("clip_type") != right_clip.get("clip_type"):
                return {}
            if int(left_clip.get("track_index", 0) or 0) != int(right_clip.get("track_index", 0) or 0):
                return {}
            if self._studio._is_track_locked(
                cursor,
                left_clip["timeline_id"],
                left_clip.get("track_type", "video"),
                int(left_clip.get("track_index", 0) or 0),
            ):
                return {}

            if int(left_clip.get("start_ms", 0) or 0) > int(right_clip.get("start_ms", 0) or 0):
                left_clip, right_clip = right_clip, left_clip
                left_id, right_id = right_id, left_id

            left_end = int(left_clip.get("end_ms", 0) or 0)
            right_start = int(right_clip.get("start_ms", 0) or 0)
            if right_start > left_end + 120:
                return {}
            left_source_end = int(left_clip.get("source_end_ms", 0) or 0)
            right_source_start = int(right_clip.get("source_start_ms", 0) or 0)
            if abs(right_source_start - left_source_end) > 180:
                return {}
            left_asset_id = int(left_clip.get("asset_id") or 0)
            right_asset_id = int(right_clip.get("asset_id") or 0)
            if left_asset_id and right_asset_id and left_asset_id != right_asset_id:
                return {}
            left_source_path = str((left_clip.get("metadata") or {}).get("source_path") or "").strip()
            right_source_path = str((right_clip.get("metadata") or {}).get("source_path") or "").strip()
            if left_source_path and right_source_path and left_source_path != right_source_path:
                return {}

            self._studio._ensure_timeline_history_baseline(cursor, project_id, left_clip["timeline_id"])

            merged_start = int(left_clip.get("start_ms", 0) or 0)
            merged_end = int(right_clip.get("end_ms", 0) or 0)
            merged_source_start = int(left_clip.get("source_start_ms", 0) or 0)
            merged_source_end = int(right_clip.get("source_end_ms", 0) or 0)
            merged_content = " ".join(
                [
                    str(left_clip.get("content", "") or "").strip(),
                    str(right_clip.get("content", "") or "").strip(),
                ]
            ).strip()
            merged_dubbing = " ".join(
                [
                    str(left_clip.get("dubbing", "") or "").strip(),
                    str(right_clip.get("dubbing", "") or "").strip(),
                ]
            ).strip()
            left_effects = left_clip.get("effects", {}) or {}
            right_effects = right_clip.get("effects", {}) or {}
            merged_effects = {**left_effects, **right_effects}
            merged_transform = left_clip.get("transform", {}) or {}
            merged_transition = left_clip.get("transition", {}) or {}
            merged_transition.pop("out", None)
            right_transition = right_clip.get("transition", {}) or {}
            if isinstance(right_transition.get("out"), dict):
                merged_transition["out"] = right_transition["out"]
            merged_metadata = {**(left_clip.get("metadata", {}) or {}), **(right_clip.get("metadata", {}) or {})}

            cursor.execute(
                """
                UPDATE timeline_clips
                SET start_ms = ?, end_ms = ?, source_start_ms = ?, source_end_ms = ?,
                    content = ?, dubbing = ?, effects_json = ?, transform_json = ?,
                    transition_json = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    merged_start,
                    merged_end,
                    merged_source_start,
                    merged_source_end,
                    merged_content,
                    merged_dubbing,
                    json.dumps(merged_effects, ensure_ascii=False),
                    json.dumps(merged_transform, ensure_ascii=False),
                    json.dumps(merged_transition, ensure_ascii=False),
                    json.dumps(merged_metadata, ensure_ascii=False),
                    left_id,
                ),
            )
            cursor.execute("DELETE FROM timeline_clips WHERE id = ?", (right_id,))
            cursor.execute(
                "UPDATE timeline_clips SET sort_order = sort_order - 1 WHERE timeline_id = ? AND sort_order > ?",
                (left_clip["timeline_id"], int(right_clip.get("sort_order", 0) or 0)),
            )
            self._studio._touch_project_timeline(cursor, project_id, left_clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, left_clip["timeline_id"], "concat_clips")
        return self._studio.get_project_timeline(project_id)

    def set_clip_flip_h(self, project_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            clip_id = int(payload.get("clip_id") or 0)
            if not clip_id:
                return {}
            row = cursor.execute(
                """
                SELECT c.*
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (clip_id, project_id),
            ).fetchone()
            if row is None:
                return {}

            clip = self._studio._serialize_clip(row)
            if clip.get("track_type") != "video":
                return {}
            if self._studio._is_track_locked(cursor, clip["timeline_id"], clip.get("track_type", "video"), int(clip.get("track_index", 0) or 0)):
                return {}
            effects = clip.get("effects", {}) or {}
            if payload.get("enabled") is None:
                effects["flip_h"] = not bool(effects.get("flip_h"))
            else:
                effects["flip_h"] = bool(payload.get("enabled"))

            self._studio._ensure_timeline_history_baseline(cursor, project_id, clip["timeline_id"])
            cursor.execute(
                "UPDATE timeline_clips SET effects_json = ? WHERE id = ?",
                (json.dumps(effects, ensure_ascii=False), clip_id),
            )
            self._studio._touch_project_timeline(cursor, project_id, clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, clip["timeline_id"], "flip_h")
        return self._studio.get_project_timeline(project_id)

    def ripple_delete_timeline_clip(self, project_id: int, clip_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT c.*
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (clip_id, project_id),
            ).fetchone()
            if row is None:
                return {}
            clip = self._studio._serialize_clip(row)
            if self._studio._is_track_locked(cursor, clip["timeline_id"], clip.get("track_type", "video"), int(clip.get("track_index", 0) or 0)):
                return {}
            duration_ms = max(0, int(clip.get("end_ms", 0) or 0) - int(clip.get("start_ms", 0) or 0))
            if duration_ms <= 0:
                return {}

            self._studio._ensure_timeline_history_baseline(cursor, project_id, clip["timeline_id"])
            cursor.execute("DELETE FROM timeline_clips WHERE id = ?", (clip_id,))
            cursor.execute(
                """
                UPDATE timeline_clips
                SET start_ms = start_ms - ?, end_ms = end_ms - ?
                WHERE timeline_id = ? AND track_type = ? AND track_index = ? AND start_ms >= ?
                """,
                (
                    duration_ms,
                    duration_ms,
                    clip["timeline_id"],
                    clip.get("track_type", "video"),
                    int(clip.get("track_index", 0) or 0),
                    int(clip.get("end_ms", 0) or 0),
                ),
            )
            self._studio._touch_project_timeline(cursor, project_id, clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, clip["timeline_id"], "ripple_delete_clip")
        return self._studio.get_project_timeline(project_id)

    def nudge_timeline_clip(self, project_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            clip_id = int(payload.get("clip_id") or 0)
            delta_ms = int(payload.get("delta_ms") or 0)
            if not clip_id or delta_ms == 0:
                return {}

            row = cursor.execute(
                """
                SELECT c.*
                FROM timeline_clips c
                JOIN timelines t ON t.id = c.timeline_id
                WHERE c.id = ? AND t.project_id = ?
                """,
                (clip_id, project_id),
            ).fetchone()
            if row is None:
                return {}
            clip = self._studio._serialize_clip(row)
            if self._studio._is_track_locked(cursor, clip["timeline_id"], clip.get("track_type", "video"), int(clip.get("track_index", 0) or 0)):
                return {}
            desired_start = int(clip.get("start_ms", 0) or 0) + delta_ms
            desired_end = int(clip.get("end_ms", 0) or 0) + delta_ms
            constrained_start, constrained_end = self._studio._constrain_clip_interval(
                cursor=cursor,
                timeline_id=clip["timeline_id"],
                track_type=clip.get("track_type", "video"),
                track_index=int(clip.get("track_index", 0) or 0),
                start_ms=desired_start,
                end_ms=desired_end,
                exclude_clip_id=clip_id,
            )
            if constrained_start == int(clip.get("start_ms", 0) or 0) and constrained_end == int(clip.get("end_ms", 0) or 0):
                return self._studio.get_project_timeline(project_id)

            self._studio._ensure_timeline_history_baseline(cursor, project_id, clip["timeline_id"])
            cursor.execute(
                "UPDATE timeline_clips SET start_ms = ?, end_ms = ? WHERE id = ?",
                (constrained_start, constrained_end, clip_id),
            )
            self._studio._touch_project_timeline(cursor, project_id, clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, clip["timeline_id"], "nudge_clip")
        return self._studio.get_project_timeline(project_id)

    def ripple_insert_timeline_clip(self, project_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            track_type = payload.get("track_type", "video")
            track_index = int(payload.get("track_index", 0) or 0)
            if self._studio._is_track_locked(cursor, timeline["id"], track_type, track_index):
                return {}
            start_ms = max(0, int(payload.get("start_ms", 0) or 0))
            end_ms = int(payload.get("end_ms", 0) or 0)
            duration_ms = max(80, end_ms - start_ms)
            end_ms = start_ms + duration_ms

            self._studio._ensure_timeline_history_baseline(cursor, project_id, timeline["id"])
            cursor.execute(
                """
                UPDATE timeline_clips
                SET start_ms = start_ms + ?, end_ms = end_ms + ?
                WHERE timeline_id = ? AND track_type = ? AND track_index = ? AND start_ms >= ?
                """,
                (duration_ms, duration_ms, timeline["id"], track_type, track_index, start_ms),
            )
            next_sort_order = cursor.execute(
                """
                SELECT COALESCE(MAX(sort_order), -1) + 1
                FROM timeline_clips
                WHERE timeline_id = ?
                """,
                (timeline["id"],),
            ).fetchone()[0]
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
                    track_type,
                    track_index,
                    start_ms,
                    end_ms,
                    payload.get("source_start_ms", 0),
                    payload.get("source_end_ms", duration_ms),
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
            self._studio._touch_project_timeline(cursor, project_id, timeline["id"])
            self._studio._push_timeline_history(cursor, project_id, timeline["id"], "ripple_insert_clip")
        return self._studio.get_project_timeline(project_id)

    def reorder_timeline_clips(self, project_id: int, payload: Dict) -> Dict:
        items = payload.get("items", [])
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._studio._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            self._studio._ensure_timeline_history_baseline(cursor, project_id, timeline["id"])

            for item in items:
                row = cursor.execute(
                    """
                    SELECT c.id
                    FROM timeline_clips c
                    WHERE c.id = ? AND c.timeline_id = ?
                    """,
                    (item["clip_id"], timeline["id"]),
                ).fetchone()
                if row is None:
                    continue
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
                        item.get("track_type", "video"),
                        item.get("track_index", 0),
                        f'{str(item.get("track_type", "video")).upper()} Track {item.get("track_index", 0)}',
                        timeline["id"],
                    ),
                )

                update_fields = [
                    "track_type = ?",
                    "track_index = ?",
                    "sort_order = ?",
                ]
                values = [
                    item.get("track_type", "video"),
                    item.get("track_index", 0),
                    item.get("sort_order", 0),
                ]
                if item.get("start_ms") is not None:
                    update_fields.append("start_ms = ?")
                    values.append(item["start_ms"])
                if item.get("end_ms") is not None:
                    update_fields.append("end_ms = ?")
                    values.append(item["end_ms"])
                values.append(item["clip_id"])
                cursor.execute(
                    f"UPDATE timeline_clips SET {', '.join(update_fields)} WHERE id = ?",
                    tuple(values),
                )

            self._studio._touch_project_timeline(cursor, project_id, timeline["id"])
            self._studio._push_timeline_history(cursor, project_id, timeline["id"], "reorder_clips")
        return self._studio.get_project_timeline(project_id)
