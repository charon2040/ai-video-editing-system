import json
from typing import Dict

from app.db.database import get_db_connection
from app.services.editor_logic_registry import normalize_transition_type


def _json_loads(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class StudioTransitionOps:
    def __init__(self, studio_service):
        self._studio = studio_service

    def apply_timeline_transition(self, project_id: int, payload: Dict) -> Dict:
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
            if left_clip.get("track_type") != right_clip.get("track_type") or int(left_clip.get("track_index", 0) or 0) != int(right_clip.get("track_index", 0) or 0):
                return {}
            if self._studio._is_track_locked(
                cursor,
                left_clip["timeline_id"],
                left_clip.get("track_type", "video"),
                int(left_clip.get("track_index", 0) or 0),
            ):
                return {}

            left_start = int(left_clip.get("start_ms", 0) or 0)
            left_end = int(left_clip.get("end_ms", 0) or 0)
            right_start = int(right_clip.get("start_ms", 0) or 0)
            right_end = int(right_clip.get("end_ms", 0) or 0)
            if left_start > right_start:
                left_clip, right_clip = right_clip, left_clip
                left_id, right_id = right_id, left_id
                left_start, left_end, right_start, right_end = right_start, right_end, left_start, left_end

            if right_start < left_start:
                return {}
            max_duration = max(80, min(left_end - left_start, right_end - right_start))
            duration_ms = int(payload.get("duration_ms", 400) or 400)
            duration_ms = max(80, min(duration_ms, max_duration))

            transition = {
                "type": normalize_transition_type(str(payload.get("transition_type") or "fade")),
                "duration_ms": duration_ms,
                "easing": str(payload.get("easing") or "linear").lower(),
            }

            self._studio._ensure_timeline_history_baseline(cursor, project_id, left_clip["timeline_id"])
            left_transition = left_clip.get("transition") or {}
            right_transition = right_clip.get("transition") or {}
            left_transition["out"] = {**transition, "pair_clip_id": right_id}
            right_transition["in"] = {**transition, "pair_clip_id": left_id}

            cursor.execute(
                "UPDATE timeline_clips SET transition_json = ? WHERE id = ?",
                (json.dumps(left_transition, ensure_ascii=False), left_id),
            )
            cursor.execute(
                "UPDATE timeline_clips SET transition_json = ? WHERE id = ?",
                (json.dumps(right_transition, ensure_ascii=False), right_id),
            )
            self._studio._touch_project_timeline(cursor, project_id, left_clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, left_clip["timeline_id"], "apply_transition")
        return self._studio.get_project_timeline(project_id)

    def clear_timeline_transition(self, project_id: int, payload: Dict) -> Dict:
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
            transition = clip.get("transition") or {}
            mode = str(payload.get("direction") or "both").lower()
            if mode not in {"in", "out", "both"}:
                mode = "both"
            self._studio._ensure_timeline_history_baseline(cursor, project_id, clip["timeline_id"])

            pair_ids = []
            if mode in {"in", "both"} and isinstance(transition.get("in"), dict):
                pair_ids.append(int(transition.get("in", {}).get("pair_clip_id") or 0))
                transition.pop("in", None)
            if mode in {"out", "both"} and isinstance(transition.get("out"), dict):
                pair_ids.append(int(transition.get("out", {}).get("pair_clip_id") or 0))
                transition.pop("out", None)
            cursor.execute(
                "UPDATE timeline_clips SET transition_json = ? WHERE id = ?",
                (json.dumps(transition, ensure_ascii=False), clip_id),
            )

            for pair_id in [pid for pid in pair_ids if pid]:
                pair_row = cursor.execute(
                    "SELECT id, transition_json FROM timeline_clips WHERE id = ? AND timeline_id = ?",
                    (pair_id, clip["timeline_id"]),
                ).fetchone()
                if pair_row is None:
                    continue
                pair_transition = _json_loads(pair_row["transition_json"], {})
                pair_in = pair_transition.get("in")
                pair_out = pair_transition.get("out")
                if isinstance(pair_in, dict) and int(pair_in.get("pair_clip_id") or 0) == clip_id:
                    pair_transition.pop("in", None)
                if isinstance(pair_out, dict) and int(pair_out.get("pair_clip_id") or 0) == clip_id:
                    pair_transition.pop("out", None)
                cursor.execute(
                    "UPDATE timeline_clips SET transition_json = ? WHERE id = ?",
                    (json.dumps(pair_transition, ensure_ascii=False), pair_id),
                )

            self._studio._touch_project_timeline(cursor, project_id, clip["timeline_id"])
            self._studio._push_timeline_history(cursor, project_id, clip["timeline_id"], "clear_transition")
        return self._studio.get_project_timeline(project_id)
