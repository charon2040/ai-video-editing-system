import json
import os
import subprocess
import uuid
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.db.database import get_db_connection
from app.services.studio_export_ops import StudioExportOps
from app.services.studio_history_ops import StudioHistoryOps
from app.services.studio_timeline_clip_ops import StudioTimelineClipOps
from app.services.studio_timeline_core_ops import StudioTimelineCoreOps
from app.services.studio_timeline_track_ops import StudioTimelineTrackOps
from app.services.studio_transition_ops import StudioTransitionOps


def _row_to_dict(row) -> Dict:
    return dict(row) if row is not None else {}


def _json_loads(value: Optional[str], default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class StudioService:
    TRACK_TYPE_ORDER = {
        "video": 0,
        "pip": 1,
        "sticker": 2,
        "subtitle": 3,
        "audio": 4,
    }
    DEFAULT_TRACKS = [
        ("video", 0),
        ("audio", 0),
        ("subtitle", 0),
        ("pip", 0),
        ("sticker", 0),
    ]

    def __init__(self):
        self._export_ops = StudioExportOps(self)
        self._history_ops = StudioHistoryOps(self)
        self._timeline_clip_ops = StudioTimelineClipOps(self)
        self._timeline_core_ops = StudioTimelineCoreOps(self)
        self._timeline_track_ops = StudioTimelineTrackOps(self)
        self._transition_ops = StudioTransitionOps(self)

    def _serialize_track(self, row) -> Dict:
        item = _row_to_dict(row)
        if not item:
            return {}
        item["track_key"] = f'{item.get("track_type", "video")}:{item.get("track_index", 0)}'
        item["display_name"] = item.get("name") or f'{str(item.get("track_type", "video")).upper()} Track {item.get("track_index", 0)}'
        item["clips"] = []
        item["is_locked"] = bool(item.get("is_locked", 0))
        item["is_muted"] = bool(item.get("is_muted", 0))
        item["is_visible"] = bool(item.get("is_visible", 1))
        return item

    def _ensure_default_tracks(self, cursor, timeline_id: int):
        for sort_order, (track_type, track_index) in enumerate(self.DEFAULT_TRACKS):
            cursor.execute(
                """
                INSERT OR IGNORE INTO timeline_tracks (
                    timeline_id, track_type, track_index, name, is_locked, is_muted, is_visible, sort_order
                )
                VALUES (?, ?, ?, ?, 0, 0, 1, ?)
                """,
                (
                    timeline_id,
                    track_type,
                    track_index,
                    f"{track_type.upper()} Track {track_index}",
                    sort_order,
                ),
            )

    def _get_track_rows(self, cursor, timeline_id: int):
        self._ensure_default_tracks(cursor, timeline_id)
        return cursor.execute(
            """
            SELECT * FROM timeline_tracks
            WHERE timeline_id = ?
            ORDER BY sort_order ASC, id ASC, track_index ASC
            """,
            (timeline_id,),
        ).fetchall()

    def _resolve_storage_path(self, raw_path: str) -> str:
        if not raw_path:
            return ""
        normalized = raw_path.strip()
        if normalized.startswith("/download/"):
            return os.path.join(settings.OUTPUT_FOLDER, os.path.basename(normalized))
        if normalized.startswith("/uploads/"):
            return os.path.join(settings.UPLOAD_FOLDER, os.path.basename(normalized))
        if os.path.isabs(normalized):
            return normalized
        candidate_output = os.path.join(settings.OUTPUT_FOLDER, os.path.basename(normalized))
        if os.path.exists(candidate_output):
            return candidate_output
        candidate_upload = os.path.join(settings.UPLOAD_FOLDER, os.path.basename(normalized))
        if os.path.exists(candidate_upload):
            return candidate_upload
        return normalized

    def _path_exists(self, file_path: str) -> bool:
        if not file_path:
            return False
        resolved = self._resolve_storage_path(file_path)
        return bool(resolved) and os.path.exists(resolved)

    def _download_url_for_path(self, file_path: str) -> str:
        if not file_path:
            return ""
        if not self._path_exists(file_path):
            return ""
        resolved_path = self._resolve_storage_path(file_path)
        normalized = os.path.normcase(os.path.normpath(os.path.abspath(resolved_path)))
        upload_root = os.path.normcase(os.path.normpath(os.path.abspath(settings.UPLOAD_FOLDER)))
        output_root = os.path.normcase(os.path.normpath(os.path.abspath(settings.OUTPUT_FOLDER)))
        if normalized.startswith(upload_root):
            return f"/uploads/{os.path.basename(resolved_path)}"
        if normalized.startswith(output_root):
            return f"/download/{os.path.basename(resolved_path)}"
        return f"/download/{os.path.basename(resolved_path)}"

    def _serialize_clip(self, row) -> Dict:
        item = _row_to_dict(row)
        if not item:
            return {}
        item["effects"] = _json_loads(item.get("effects_json"), {})
        item["transform"] = _json_loads(item.get("transform_json"), {})
        item["transition"] = _json_loads(item.get("transition_json"), {})
        item["metadata"] = _json_loads(item.get("metadata_json"), {})
        source_path = item["metadata"].get("source_path", "")
        item["source_exists"] = self._path_exists(source_path)
        item["preview_url"] = self._download_url_for_path(source_path)
        return item

    def _serialize_timeline(self, row, clips: Optional[List[Dict]] = None, track_rows=None) -> Dict:
        item = _row_to_dict(row)
        if not item:
            return {}
        item["render_blueprint"] = _json_loads(item.get("render_blueprint_json"), {})
        item["source_video_exists"] = self._path_exists(item.get("source_video_path", ""))
        item["source_video_url"] = self._download_url_for_path(item.get("source_video_path", ""))
        item["source_edl_url"] = self._download_url_for_path(item.get("source_edl_path", ""))
        item["clips"] = clips or []
        item["tracks"] = self._build_tracks(item["clips"], track_rows or [])
        return item

    def _build_tracks(self, clips: List[Dict], track_rows: List[Dict]) -> List[Dict]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for row in track_rows:
            track = self._serialize_track(row)
            grouped[track["track_key"]] = track

        for clip in clips:
            track_type = clip.get("track_type", "video")
            track_index = int(clip.get("track_index", 0) or 0)
            track_key = f"{track_type}:{track_index}"
            if track_key not in grouped:
                grouped[track_key] = {
                    "track_key": track_key,
                    "track_type": track_type,
                    "track_index": track_index,
                    "display_name": f"{track_type.upper()} Track {track_index}",
                    "clips": [],
                    "is_locked": False,
                    "is_muted": False,
                    "is_visible": True,
                    "sort_order": 999,
                }
            grouped[track_key]["clips"].append(clip)

        return sorted(
            grouped.values(),
            key=lambda item: (
                item.get("sort_order", 999),
                self.TRACK_TYPE_ORDER.get(item["track_type"], 99),
                item["track_index"],
            ),
        )

    def _serialize_asset(self, row) -> Dict:
        item = _row_to_dict(row)
        if not item:
            return {}
        item["file_exists"] = self._path_exists(item.get("file_path", ""))
        item["download_url"] = self._download_url_for_path(item.get("file_path", ""))
        return item

    def _extract_audio_asset(self, cursor, project_id: int, asset_item: Dict) -> Dict:
        source_path = self._resolve_storage_path(asset_item.get("file_path", ""))
        if not source_path or not os.path.exists(source_path):
            return {}

        base_name = os.path.splitext(os.path.basename(asset_item.get("name") or asset_item.get("file_path") or "asset"))[0]
        safe_name = "".join([c for c in base_name if c.isalnum() or c in ("-", "_")]).strip() or "asset"
        output_name = f"{safe_name}_audio_{uuid.uuid4().hex}.mp3"
        os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
        output_path = os.path.join(settings.UPLOAD_FOLDER, output_name)

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", source_path, "-vn", "-acodec", "mp3", output_path],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return {}

        duration_ms = int(asset_item.get("duration_ms") or 0)
        cursor.execute(
            """
            INSERT INTO media_assets (project_id, name, file_type, file_path, duration_ms, transcript_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                f"{base_name} (audio)",
                "mp3",
                output_path,
                duration_ms,
                "ready",
            ),
        )
        new_id = cursor.lastrowid
        row = cursor.execute("SELECT * FROM media_assets WHERE id = ?", (new_id,)).fetchone()
        return self._serialize_asset(row)

    def _strip_audio_from_asset(self, cursor, project_id: int, asset_item: Dict) -> Dict:
        source_path = self._resolve_storage_path(asset_item.get("file_path", ""))
        if not source_path or not os.path.exists(source_path):
            return {}

        base_name = os.path.splitext(os.path.basename(asset_item.get("name") or asset_item.get("file_path") or "asset"))[0]
        safe_name = "".join([c for c in base_name if c.isalnum() or c in ("-", "_")]).strip() or "asset"
        source_ext = os.path.splitext(source_path)[1] or ".mp4"
        output_name = f"{safe_name}_silent_{uuid.uuid4().hex}{source_ext}"
        os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
        output_path = os.path.join(settings.UPLOAD_FOLDER, output_name)

        try:
            # Prefer stream copy to keep the operation fast and avoid needless re-encoding.
            subprocess.run(
                ["ffmpeg", "-y", "-i", source_path, "-map", "0:v:0", "-c:v", "copy", "-an", output_path],
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception:
            return {}

        duration_ms = int(asset_item.get("duration_ms") or 0)
        cursor.execute(
            """
            INSERT INTO media_assets (project_id, name, file_type, file_path, duration_ms, transcript_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                f"{base_name} (silent)",
                asset_item.get("file_type") or "mp4",
                output_path,
                duration_ms,
                "ready",
            ),
        )
        new_id = cursor.lastrowid
        row = cursor.execute("SELECT * FROM media_assets WHERE id = ?", (new_id,)).fetchone()
        return self._serialize_asset(row)

    def _get_project_timeline_row(self, cursor, project_id: int):
        return cursor.execute("SELECT * FROM timelines WHERE project_id = ?", (project_id,)).fetchone()

    def _touch_project_timeline(self, cursor, project_id: int, timeline_id: int):
        cursor.execute(
            "UPDATE timelines SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (timeline_id,),
        )
        cursor.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,),
        )

    def _is_track_locked(self, cursor, timeline_id: int, track_type: str, track_index: int) -> bool:
        row = cursor.execute(
            """
            SELECT is_locked
            FROM timeline_tracks
            WHERE timeline_id = ? AND track_type = ? AND track_index = ?
            LIMIT 1
            """,
            (timeline_id, track_type, int(track_index or 0)),
        ).fetchone()
        if row is None:
            return False
        return bool(row["is_locked"])

    def _constrain_clip_interval(
        self,
        cursor,
        timeline_id: int,
        track_type: str,
        track_index: int,
        start_ms: int,
        end_ms: int,
        exclude_clip_id: Optional[int] = None,
    ) -> tuple[int, int]:
        min_duration = 80
        start = int(start_ms or 0)
        end = int(end_ms or 0)
        duration = max(min_duration, end - start)

        rows = cursor.execute(
            """
            SELECT id, start_ms, end_ms
            FROM timeline_clips
            WHERE timeline_id = ? AND track_type = ? AND track_index = ? AND (? IS NULL OR id != ?)
            ORDER BY start_ms ASC, end_ms ASC, id ASC
            """,
            (timeline_id, track_type, track_index, exclude_clip_id, exclude_clip_id),
        ).fetchall()

        prev_end = 0
        next_start = None
        for row in rows:
            clip_start = int(row["start_ms"] or 0)
            clip_end = int(row["end_ms"] or 0)
            if clip_start <= start:
                prev_end = max(prev_end, clip_end)
                continue
            next_start = clip_start
            break

        start = max(start, prev_end)
        if next_start is not None and start + duration > next_start:
            candidate_start = next_start - duration
            if candidate_start >= prev_end:
                start = candidate_start
            else:
                start = prev_end
                duration = max(min_duration, next_start - start)
        end = start + duration

        if next_start is not None and end > next_start:
            end = next_start
        if end <= start:
            end = start + min_duration
            if next_start is not None:
                end = min(end, next_start)
            if end <= start:
                end = start
        return start, end

    def _build_timeline_history_snapshot(self, cursor, timeline_id: int) -> Dict[str, Any]:
        return self._history_ops.build_timeline_history_snapshot(cursor, timeline_id)

    def _push_timeline_history(self, cursor, project_id: int, timeline_id: int, action: str):
        return self._history_ops.push_timeline_history(cursor, project_id, timeline_id, action)

    def _ensure_timeline_history_baseline(self, cursor, project_id: int, timeline_id: int):
        return self._history_ops.ensure_timeline_history_baseline(cursor, project_id, timeline_id)

    def _restore_timeline_history_row(self, cursor, project_id: int, timeline_id: int, history_row) -> bool:
        return self._history_ops.restore_timeline_history_row(cursor, project_id, timeline_id, history_row)

    def _serialize_export(self, row) -> Dict:
        item = _row_to_dict(row)
        if not item:
            return {}
        item["render_config"] = _json_loads(item.get("render_config_json"), {})
        item["output_url"] = (
            item.get("output_path", "")
            if str(item.get("output_path", "")).startswith("/download/")
            else ""
        )
        return item

    def get_blueprint(self) -> Dict:
        return {
            "product_positioning": {
                "name": "AI Online Video Studio",
                "value": "面向内容运营、赛事速递和短视频团队的在线智能剪辑平台",
            },
            "core_modules": [
                "项目工作台",
                "素材库",
                "AI 导演",
                "在线时间线",
                "特效与字幕面板",
                "异步导出中心",
                "数据看板",
            ],
            "database_design": {
                "projects": "项目主表，记录业务场景、宽高比和协作状态",
                "media_assets": "素材表，记录上传文件、路径和识别状态",
                "timelines": "时间线主表，保存源成片路径、蓝图和版本信息",
                "timeline_clips": "时间线片段表，保存轨道、变换、转场和元数据",
                "export_jobs": "导出任务表，保存渲染配置、错误信息和进度状态",
                "effect_presets": "产品内置特效库，支持高亮、模糊等预设",
            },
            "backend_architecture": [
                "API 层：FastAPI 提供项目、时间线、特效编辑和导出任务接口",
                "Service 层：ASR/LLM/TTS/FFmpeg 与时间线编排逻辑解耦",
                "Worker 层：后台线程轮询 queued 任务并异步渲染",
                "Data 层：SQLite 原型库已支持字段迁移，后续可切到 PostgreSQL",
                "Storage 层：uploads/output/audio 目录管理原始素材和导出结果",
            ],
            "frontend_pages": [
                "首页/控制台",
                "项目列表",
                "项目详情",
                "AI 智能剪辑面板",
                "在线时间线编辑台",
                "特效与字幕面板",
                "异步导出中心",
            ],
        }

    def get_overview(self) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            total_projects = cursor.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            total_assets = cursor.execute("SELECT COUNT(*) FROM media_assets").fetchone()[0]
            total_exports = cursor.execute("SELECT COUNT(*) FROM export_jobs").fetchone()[0]
            queued_exports = cursor.execute(
                "SELECT COUNT(*) FROM export_jobs WHERE status IN ('queued', 'processing')"
            ).fetchone()[0]
            recent_projects = [
                dict(row)
                for row in cursor.execute(
                    "SELECT id, name, status, scenario, updated_at FROM projects ORDER BY updated_at DESC, id DESC LIMIT 5"
                ).fetchall()
            ]
        return {
            "metrics": {
                "projects": total_projects,
                "assets": total_assets,
                "exports": total_exports,
                "queued_exports": queued_exports,
            },
            "recent_projects": recent_projects,
        }

    def list_projects(self) -> List[Dict]:
        with get_db_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    p.description,
                    p.scenario,
                    p.status,
                    p.aspect_ratio,
                    p.created_at,
                    p.updated_at,
                    COUNT(DISTINCT a.id) AS asset_count,
                    COUNT(DISTINCT e.id) AS export_count
                FROM projects p
                LEFT JOIN media_assets a ON a.project_id = p.id
                LEFT JOIN export_jobs e ON e.project_id = p.id
                GROUP BY p.id
                ORDER BY p.updated_at DESC, p.id DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_effect_presets(self) -> List[Dict]:
        with get_db_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM effect_presets ORDER BY is_system DESC, id ASC"
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["config"] = _json_loads(item.get("config_json"), {})
            items.append(item)
        return items

    def create_project(self, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO projects (name, description, scenario, aspect_ratio, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    payload["name"],
                    payload.get("description", ""),
                    payload.get("scenario", "sports_digest"),
                    payload.get("aspect_ratio", "16:9"),
                    "draft",
                ),
            )
            project_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO timelines (
                    project_id, name, resolution, fps, script, status,
                    source_video_path, source_edl_path, render_blueprint_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (project_id, "主时间线", "1920x1080", 30, "", "draft", "", "", "{}"),
            )
            timeline_id = cursor.lastrowid
            self._ensure_default_tracks(cursor, timeline_id)
        return self.get_project_detail(project_id)

    def create_asset(self, project_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO media_assets (project_id, name, file_type, file_path, duration_ms, transcript_status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    payload["name"],
                    payload["file_type"],
                    self._resolve_storage_path(payload.get("file_path", "")),
                    payload.get("duration_ms", 0),
                    payload.get("transcript_status", "pending"),
                ),
            )
            asset_id = cursor.lastrowid
            row = cursor.execute("SELECT * FROM media_assets WHERE id = ?", (asset_id,)).fetchone()
        return self._serialize_asset(row)

    def register_existing_asset(self, project_id: int, payload: Dict) -> Dict:
        file_path = self._resolve_storage_path(payload.get("file_path", ""))
        if not file_path or not os.path.exists(file_path):
            return {}
        with get_db_connection() as connection:
            cursor = connection.cursor()
            existing = cursor.execute(
                "SELECT * FROM media_assets WHERE project_id = ? AND file_path = ? ORDER BY id DESC LIMIT 1",
                (project_id, file_path),
            ).fetchone()
            if existing is not None:
                return self._serialize_asset(existing)

        return self.create_asset(
            project_id,
            {
                "name": payload.get("name") or os.path.basename(file_path),
                "file_type": payload.get("file_type") or "media",
                "file_path": file_path,
                "duration_ms": int(payload.get("duration_ms") or 0),
                "transcript_status": payload.get("transcript_status") or "ready",
            },
        )

    def extract_audio_from_asset(self, project_id: int, asset_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            asset = cursor.execute(
                "SELECT * FROM media_assets WHERE id = ? AND project_id = ?",
                (asset_id, project_id),
            ).fetchone()
            if asset is None:
                return {}
            return self._extract_audio_asset(cursor, project_id, dict(asset))

    def get_project_detail(self, project_id: int) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            project = cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if project is None:
                return {}

            timeline = cursor.execute("SELECT * FROM timelines WHERE project_id = ?", (project_id,)).fetchone()
            clips: List[Dict[str, Any]] = []
            track_rows = []
            if timeline is not None:
                track_rows = self._get_track_rows(cursor, timeline["id"])
                clip_rows = cursor.execute(
                    "SELECT * FROM timeline_clips WHERE timeline_id = ? ORDER BY sort_order ASC, id ASC",
                    (timeline["id"],),
                ).fetchall()
                clips = [self._serialize_clip(clip) for clip in clip_rows]

            assets = [
                {
                    **dict(row),
                    "file_exists": self._path_exists(dict(row).get("file_path", "")),
                    "download_url": self._download_url_for_path(dict(row).get("file_path", "")),
                }
                for row in cursor.execute(
                    "SELECT * FROM media_assets WHERE project_id = ? ORDER BY id DESC",
                    (project_id,),
                ).fetchall()
            ]
            exports = [
                self._serialize_export(row)
                for row in cursor.execute(
                    "SELECT * FROM export_jobs WHERE project_id = ? ORDER BY id DESC",
                    (project_id,),
                ).fetchall()
            ]

        project_data = dict(project)
        project_data["assets"] = assets
        project_data["timeline"] = self._serialize_timeline(timeline, clips, track_rows) if timeline else {}
        project_data["exports"] = exports
        return project_data

    def delete_asset(self, project_id: int, asset_id: int) -> bool:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            asset = cursor.execute(
                "SELECT * FROM media_assets WHERE id = ? AND project_id = ?",
                (asset_id, project_id),
            ).fetchone()
            if asset is None:
                return False

            file_path = asset["file_path"]
            resolved_path = self._resolve_storage_path(file_path)
            cursor.execute(
                "DELETE FROM timeline_clips WHERE asset_id = ? AND timeline_id IN (SELECT id FROM timelines WHERE project_id = ?)",
                (asset_id, project_id),
            )
            cursor.execute(
                "DELETE FROM media_assets WHERE id = ? AND project_id = ?",
                (asset_id, project_id),
            )

        if resolved_path and os.path.exists(resolved_path):
            try:
                os.remove(resolved_path)
            except OSError:
                pass
        return True

    def cleanup_missing_assets(self, project_id: int) -> Dict[str, int]:
        removed_assets = 0
        removed_clips = 0
        with get_db_connection() as connection:
            cursor = connection.cursor()
            assets = cursor.execute(
                "SELECT * FROM media_assets WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            missing_asset_ids = []
            for asset in assets:
                if not self._path_exists(asset["file_path"]):
                    missing_asset_ids.append(asset["id"])

            if missing_asset_ids:
                placeholders = ",".join(["?"] * len(missing_asset_ids))
                removed_clips += cursor.execute(
                    f"DELETE FROM timeline_clips WHERE asset_id IN ({placeholders}) AND timeline_id IN (SELECT id FROM timelines WHERE project_id = ?)",
                    (*missing_asset_ids, project_id),
                ).rowcount
                removed_assets += cursor.execute(
                    f"DELETE FROM media_assets WHERE id IN ({placeholders}) AND project_id = ?",
                    (*missing_asset_ids, project_id),
                ).rowcount

            clip_rows = cursor.execute(
                "SELECT * FROM timeline_clips WHERE timeline_id IN (SELECT id FROM timelines WHERE project_id = ?)",
                (project_id,),
            ).fetchall()
            stale_clip_ids = []
            for clip in clip_rows:
                clip_data = self._serialize_clip(clip)
                if clip_data.get("track_type") == "video" and not clip_data.get("source_exists", True):
                    stale_clip_ids.append(clip["id"])

            if stale_clip_ids:
                placeholders = ",".join(["?"] * len(stale_clip_ids))
                removed_clips += cursor.execute(
                    f"DELETE FROM timeline_clips WHERE id IN ({placeholders})",
                    tuple(stale_clip_ids),
                ).rowcount

        return {
            "removed_assets": removed_assets,
            "removed_clips": removed_clips,
        }

    def get_project_timeline(self, project_id: int) -> Dict:
        detail = self.get_project_detail(project_id)
        return detail.get("timeline", {})

    def get_timeline_by_id(self, timeline_id: int) -> Dict:
        return self._timeline_core_ops.get_timeline_by_id(timeline_id)

    def upsert_timeline(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_core_ops.upsert_timeline(project_id, payload)

    def update_timeline_clip(self, project_id: int, clip_id: int, payload: Dict) -> Dict:
        return self._timeline_core_ops.update_timeline_clip(project_id, clip_id, payload)

    def create_timeline_clip(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_core_ops.create_timeline_clip(project_id, payload)

    def delete_timeline_clip(self, project_id: int, clip_id: int) -> bool:
        return self._timeline_core_ops.delete_timeline_clip(project_id, clip_id)

    def ripple_delete_timeline_clip(self, project_id: int, clip_id: int) -> Dict:
        return self._timeline_clip_ops.ripple_delete_timeline_clip(project_id, clip_id)

    def nudge_timeline_clip(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_clip_ops.nudge_timeline_clip(project_id, payload)

    def ripple_split_timeline_clip(self, project_id: int, clip_id: int, split_ms: int, keep: str = "right") -> Dict:
        return self._timeline_clip_ops.ripple_split_timeline_clip(project_id, clip_id, split_ms, keep)

    def ripple_insert_timeline_clip(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_clip_ops.ripple_insert_timeline_clip(project_id, payload)

    def split_timeline_clip(self, project_id: int, clip_id: int, split_ms: int, keep: str = "both") -> Dict:
        return self._timeline_clip_ops.split_timeline_clip(project_id, clip_id, split_ms, keep)

    def separate_audio_from_timeline_clip(self, project_id: int, clip_id: int) -> Dict:
        return self._timeline_clip_ops.separate_audio_from_timeline_clip(project_id, clip_id)

    def concat_timeline_clips(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_clip_ops.concat_timeline_clips(project_id, payload)

    def set_clip_flip_h(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_clip_ops.set_clip_flip_h(project_id, payload)

    def apply_timeline_transition(self, project_id: int, payload: Dict) -> Dict:
        return self._transition_ops.apply_timeline_transition(project_id, payload)

    def clear_timeline_transition(self, project_id: int, payload: Dict) -> Dict:
        return self._transition_ops.clear_timeline_transition(project_id, payload)

    def reorder_timeline_clips(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_clip_ops.reorder_timeline_clips(project_id, payload)

    def get_timeline_history_state(self, project_id: int) -> Dict[str, Any]:
        return self._history_ops.get_timeline_history_state(project_id)

    def undo_timeline(self, project_id: int) -> Dict:
        return self._history_ops.undo_timeline(project_id)

    def redo_timeline(self, project_id: int) -> Dict:
        return self._history_ops.redo_timeline(project_id)

    def recover_timeline_history(self, project_id: int) -> Dict:
        return self._history_ops.recover_timeline_history(project_id)

    def clear_timeline_clips(self, project_id: int) -> Dict:
        return self._timeline_track_ops.clear_timeline_clips(project_id)

    def reset_project_data(self, project_id: int, *, clear_assets: bool = True) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline = self._get_project_timeline_row(cursor, project_id)
            if timeline is None:
                return {}
            timeline_id = int(timeline["id"])

            # 获取所有相关素材路径
            asset_rows = cursor.execute(
                "SELECT file_path FROM media_assets WHERE project_id = ?", (project_id,)
            ).fetchall()
            asset_paths = [row["file_path"] for row in asset_rows]

            # 获取所有导出任务路径
            export_rows = cursor.execute(
                "SELECT output_path FROM export_jobs WHERE project_id = ?", (project_id,)
            ).fetchall()
            export_paths = [row["output_path"] for row in export_rows]

            cursor.execute("DELETE FROM timeline_clips WHERE timeline_id = ?", (timeline_id,))
            cursor.execute("DELETE FROM timeline_tracks WHERE timeline_id = ?", (timeline_id,))
            self._ensure_default_tracks(cursor, timeline_id)

            cursor.execute(
                "DELETE FROM timeline_histories WHERE project_id = ? AND timeline_id = ?",
                (project_id, timeline_id),
            )
            cursor.execute(
                "UPDATE timelines SET current_history_id = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (timeline_id,),
            )
            cursor.execute("DELETE FROM export_jobs WHERE project_id = ?", (project_id,))

            if clear_assets:
                cursor.execute("DELETE FROM media_assets WHERE project_id = ?", (project_id,))

            cursor.execute(
                "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (project_id,),
            )

        # 清理物理磁盘文件
        if clear_assets:
            for path in asset_paths:
                resolved = self._resolve_storage_path(path)
                if resolved and os.path.exists(resolved) and os.path.isfile(resolved):
                    try:
                        os.remove(resolved)
                    except OSError:
                        pass

        for path in export_paths:
            resolved = self._resolve_storage_path(path)
            if resolved and os.path.exists(resolved) and os.path.isfile(resolved):
                try:
                    os.remove(resolved)
                except OSError:
                    pass

        # 清理相关音频缓存文件
        if clear_assets:
            for file_name in os.listdir(settings.AUDIO_FOLDER):
                file_path = os.path.join(settings.AUDIO_FOLDER, file_name)
                if os.path.isfile(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass

        return self.get_project_detail(project_id)

    def create_timeline_track(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_track_ops.create_timeline_track(project_id, payload)

    def delete_timeline_track(self, project_id: int, track_id: int) -> bool:
        return self._timeline_track_ops.delete_timeline_track(project_id, track_id)

    def update_timeline_track(self, project_id: int, track_id: int, payload: Dict) -> Dict:
        return self._timeline_track_ops.update_timeline_track(project_id, track_id, payload)

    def reorder_timeline_tracks(self, project_id: int, payload: Dict) -> Dict:
        return self._timeline_track_ops.reorder_timeline_tracks(project_id, payload)

    def create_export_job(self, project_id: int, payload: Dict) -> Dict:
        return self._export_ops.create_export_job(project_id, payload)

    def list_export_jobs(self, project_id: int) -> List[Dict]:
        return self._export_ops.list_export_jobs(project_id)

    def get_export_job(self, project_id: int, job_id: int) -> Dict:
        return self._export_ops.get_export_job(project_id, job_id)

    def get_export_job_by_id(self, job_id: int) -> Dict:
        return self._export_ops.get_export_job_by_id(job_id)

    def fetch_next_queued_export_job(self) -> Dict:
        return self._export_ops.fetch_next_queued_export_job()

    def update_export_job_status(
        self,
        job_id: int,
        *,
        status: str,
        progress: Optional[int] = None,
        output_path: Optional[str] = None,
        error_message: Optional[str] = None,
        mark_started: bool = False,
        mark_finished: bool = False,
    ) -> Dict:
        return self._export_ops.update_export_job_status(
            job_id,
            status=status,
            progress=progress,
            output_path=output_path,
            error_message=error_message,
            mark_started=mark_started,
            mark_finished=mark_finished,
        )


studio_service = StudioService()
