import json
from typing import Dict, List, Optional

from app.db.database import get_db_connection


class StudioExportOps:
    def __init__(self, studio_service):
        self._studio = studio_service

    def create_export_job(self, project_id: int, payload: Dict) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            timeline_id = payload.get("timeline_id")
            timeline = None
            if timeline_id:
                timeline = cursor.execute("SELECT * FROM timelines WHERE id = ?", (timeline_id,)).fetchone()
            if timeline is None:
                timeline = cursor.execute("SELECT * FROM timelines WHERE project_id = ?", (project_id,)).fetchone()
                timeline_id = timeline["id"] if timeline else None

            render_config = {
                "profile": payload.get("job_type", "online_render"),
                "burn_subtitles": True,
                "quality": "standard",
                "apply_clip_effects": True,
                **payload.get("render_config", {}),
            }
            source_video_path = self._studio._resolve_storage_path(payload.get("source_video_path", ""))
            if not source_video_path and timeline is not None:
                source_video_path = timeline["source_video_path"]

            cursor.execute(
                """
                INSERT INTO export_jobs (
                    project_id, timeline_id, job_type, status, progress, output_path,
                    render_config_json, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    timeline_id,
                    payload.get("job_type", "online_render"),
                    "queued",
                    0,
                    source_video_path,
                    json.dumps(render_config, ensure_ascii=False),
                    "",
                ),
            )
            job_id = cursor.lastrowid
            row = cursor.execute("SELECT * FROM export_jobs WHERE id = ?", (job_id,)).fetchone()
            cursor.execute(
                "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (project_id,),
            )
        return self._studio._serialize_export(row)

    def list_export_jobs(self, project_id: int) -> List[Dict]:
        with get_db_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM export_jobs WHERE project_id = ? ORDER BY id DESC",
                (project_id,),
            ).fetchall()
        return [self._studio._serialize_export(row) for row in rows]

    def get_export_job(self, project_id: int, job_id: int) -> Dict:
        with get_db_connection() as connection:
            row = connection.execute(
                "SELECT * FROM export_jobs WHERE project_id = ? AND id = ?",
                (project_id, job_id),
            ).fetchone()
        return self._studio._serialize_export(row)

    def get_export_job_by_id(self, job_id: int) -> Dict:
        with get_db_connection() as connection:
            row = connection.execute("SELECT * FROM export_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._studio._serialize_export(row)

    def fetch_next_queued_export_job(self) -> Dict:
        with get_db_connection() as connection:
            cursor = connection.cursor()
            row = cursor.execute(
                """
                SELECT * FROM export_jobs
                WHERE status = 'queued'
                ORDER BY id ASC
                LIMIT 1
                """
            ).fetchone()
        return self._studio._serialize_export(row)

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
        with get_db_connection() as connection:
            cursor = connection.cursor()
            current = cursor.execute("SELECT * FROM export_jobs WHERE id = ?", (job_id,)).fetchone()
            if current is None:
                return {}

            next_progress = progress if progress is not None else current["progress"]
            next_output_path = output_path if output_path is not None else current["output_path"]
            next_error_message = error_message if error_message is not None else current["error_message"]
            started_at_sql = ", started_at = CURRENT_TIMESTAMP" if mark_started else ""
            finished_at_sql = ", finished_at = CURRENT_TIMESTAMP" if mark_finished else ""

            cursor.execute(
                f"""
                UPDATE export_jobs
                SET status = ?, progress = ?, output_path = ?, error_message = ?,
                    updated_at = CURRENT_TIMESTAMP
                    {started_at_sql}
                    {finished_at_sql}
                WHERE id = ?
                """,
                (status, next_progress, next_output_path, next_error_message, job_id),
            )
            updated = cursor.execute("SELECT * FROM export_jobs WHERE id = ?", (job_id,)).fetchone()
        return self._studio._serialize_export(updated)
