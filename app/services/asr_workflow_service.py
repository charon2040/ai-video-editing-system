from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

from app.core.config import settings
from app.core.db import app_db
from app.services.asr_service import asr_service
from app.services.task_event_service import now_iso


logger = logging.getLogger(__name__)

UpdateTaskCallback = Callable[..., Dict[str, Any]]
RecordTaskEventCallback = Callable[..., None]


@dataclass(frozen=True)
class ASRWorkflowResult:
    subtitles: List[Dict[str, Any]]
    audio_path: Path
    cache_hit: bool


class ASRWorkflowService:
    def cache_audio_path(self, source_hash: str) -> Path:
        return settings.audio_dir / f"cache_{source_hash[:16]}.wav"

    def load_or_build_asr(
        self,
        *,
        task_id: str,
        source_path: Path,
        source_hash: str,
        source_size: int,
        original_filename: str,
        update_task: UpdateTaskCallback,
        record_task_event: RecordTaskEventCallback,
    ) -> ASRWorkflowResult:
        cache_audio_path = self.cache_audio_path(source_hash)
        cached = app_db.get_asr_cache(source_hash)
        if cached:
            logger.info(
                "Task %s ASR cache hit: hash=%s subtitle_count=%s",
                task_id,
                source_hash[:12],
                cached.get("subtitle_count", 0),
            )
            if not cache_audio_path.exists():
                logger.info("Task %s rebuilding cached audio file because it is missing.", task_id)
                if not asr_service.extract_audio_from_video(str(source_path), str(cache_audio_path)):
                    raise RuntimeError("音频抽取失败，请确认 FFmpeg 可用且视频文件正常。")
            update_task(
                task_id,
                stage="transcribing",
                progress=35,
                message="命中 ASR 缓存，正在复用字幕结果",
                artifacts={"audio_url": f"/audio/{cache_audio_path.name}"},
                result={
                    "subtitle_count": int(cached.get("subtitle_count", 0)),
                    "asr_cache_hit": True,
                },
            )
            record_task_event(
                task_id,
                event_type="asr_cache_hit",
                detail={
                    "subtitle_count": int(cached.get("subtitle_count", 0)),
                    "source_hash": source_hash[:12],
                },
            )
            return ASRWorkflowResult(
                subtitles=cached.get("subtitles", []),
                audio_path=cache_audio_path,
                cache_hit=True,
            )

        update_task(
            task_id,
            status="running",
            stage="extracting_audio",
            progress=10,
            message="正在抽取音频",
            result={"asr_cache_hit": False},
        )
        if not asr_service.extract_audio_from_video(str(source_path), str(cache_audio_path)):
            raise RuntimeError("音频抽取失败，请确认 FFmpeg 可用且视频文件正常。")
        logger.info("Task %s audio extracted: %s", task_id, cache_audio_path.name)

        update_task(
            task_id,
            stage="transcribing",
            progress=35,
            message="正在使用 FunASR 识别字幕与时间戳",
            artifacts={"audio_url": f"/audio/{cache_audio_path.name}"},
        )
        subtitles = asr_service.process_audio(str(cache_audio_path))
        if not subtitles:
            raise RuntimeError("FunASR 没有返回有效字幕，无法继续剪辑。")
        logger.info("Task %s transcribed: subtitle_count=%s", task_id, len(subtitles))
        record_task_event(
            task_id,
            event_type="asr_completed",
            detail={
                "subtitle_count": len(subtitles),
                "source_hash": source_hash[:12],
            },
        )

        app_db.upsert_asr_cache(
            source_hash=source_hash,
            original_filename=original_filename,
            source_size=source_size,
            audio_path=str(cache_audio_path),
            subtitles=subtitles,
            now_iso=now_iso(),
        )
        return ASRWorkflowResult(
            subtitles=subtitles,
            audio_path=cache_audio_path,
            cache_hit=False,
        )


asr_workflow_service = ASRWorkflowService()

