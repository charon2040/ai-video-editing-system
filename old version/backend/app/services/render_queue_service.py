import os
import threading
import time
from typing import Dict

from app.core.config import settings
from app.services.advanced_render_service import advanced_render_service
from app.services.studio_service import studio_service


class RenderQueueService:
    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run_loop(self):
        while not self._stop_event.is_set():
            job = studio_service.fetch_next_queued_export_job()
            if not job:
                time.sleep(1.5)
                continue
            self._process_job(job)

    def _resolve_source_video(self, job: Dict, timeline: Dict) -> str:
        output_path = job.get("output_path", "")
        if output_path and os.path.exists(output_path):
            return output_path
        if timeline.get("source_video_path") and os.path.exists(timeline["source_video_path"]):
            return timeline["source_video_path"]
        return ""

    def _process_job(self, job: Dict):
        job_id = job["id"]
        studio_service.update_export_job_status(
            job_id,
            status="processing",
            progress=5,
            error_message="",
            mark_started=True,
        )

        try:
            timeline_id = job.get("timeline_id")
            if not timeline_id:
                raise RuntimeError("导出任务缺少 timeline_id")

            timeline = studio_service.get_timeline_by_id(timeline_id)
            if not timeline:
                raise RuntimeError("未找到导出对应的时间线")

            source_video_path = self._resolve_source_video(job, timeline)
            if not source_video_path:
                raise RuntimeError("未找到可渲染的视频源，请先完成一次 AI 剪辑并保存时间线")

            studio_service.update_export_job_status(job_id, status="processing", progress=35)

            output_basename = f"export_job_{job_id}.mp4"
            output_video_path = os.path.join(settings.OUTPUT_FOLDER, output_basename)
            render_config = job.get("render_config", {})
            if not advanced_render_service.render_timeline_export(
                source_video_path, output_video_path, timeline, render_config
            ):
                raise RuntimeError("FFmpeg 渲染失败，请检查视频源或特效参数")

            studio_service.update_export_job_status(job_id, status="processing", progress=95)
            studio_service.update_export_job_status(
                job_id,
                status="completed",
                progress=100,
                output_path=f"/download/{output_basename}",
                error_message="",
                mark_finished=True,
            )
        except Exception as exc:
            studio_service.update_export_job_status(
                job_id,
                status="failed",
                progress=0,
                error_message=str(exc),
                mark_finished=True,
            )


render_queue_service = RenderQueueService()
