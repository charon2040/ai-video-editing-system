from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from app.core.config import settings
from app.services.voice_binding_service import voice_binding_service


@dataclass(frozen=True)
class TaskRunContext:
    task_id: str
    user_id: str
    original_filename: str
    request_text: str
    request_mode: str
    project_context: str
    duration_seconds: int
    style: str
    enable_dubbing: bool
    voice_source: str
    voice_mode: str
    voice_profile_id: str
    tts_voice: str
    voice_profile_label: str
    voice_profile_ref: str
    tts_speed: float
    keep_original_audio: bool
    uploaded_voiceover_path: Path
    uploaded_voiceover_duration_ms: int
    source_path: Path
    source_hash: str
    source_size: int
    output_path: Path
    subtitle_work_path: Path
    raw_output_path: Path
    srt_path: Path
    ass_path: Path
    edl_path: Path
    voiceover_path: Path


class TaskRunContextService:
    def build_context(self, *, task_id: str, task: Dict[str, Any]) -> TaskRunContext:
        payload = task.get("payload", {}) or {}
        source_path = Path(task.get("source_path", ""))
        output_base = f"{task_id}_{source_path.stem}"
        user_id = str(task.get("user_id", "") or "local").strip() or "local"

        voice_profile_id = str(payload.get("voice_profile_id", "") or "").strip()
        tts_voice = str(payload.get("tts_voice", settings.tts_default_voice) or settings.tts_default_voice)
        voice_profile_label = str(payload.get("voice_profile_label", "") or tts_voice).strip()
        voice_source = str(payload.get("voice_source", "") or "tts").strip().lower()
        if voice_source not in {"tts", "uploaded_voiceover"}:
            voice_source = "tts"
        voice_mode = voice_binding_service.infer_voice_mode(
            voice_mode=str(payload.get("voice_mode", "") or ""),
            voice_profile_id=voice_profile_id,
            tts_voice=tts_voice,
            user_id=user_id,
        )

        return TaskRunContext(
            task_id=task_id,
            user_id=user_id,
            original_filename=str(payload.get("original_filename", "") or ""),
            request_text=str(payload.get("request_text", "") or ""),
            request_mode=str(payload.get("request_mode", "requirements") or "requirements"),
            project_context=str(payload.get("project_context", "") or "").strip(),
            duration_seconds=int(payload.get("duration_seconds", 0) or 0),
            style=str(payload.get("style", "") or ""),
            enable_dubbing=bool(payload.get("enable_dubbing", False)),
            voice_source=voice_source,
            voice_mode=voice_mode,
            voice_profile_id=voice_profile_id,
            tts_voice=tts_voice,
            voice_profile_label=voice_profile_label,
            voice_profile_ref=voice_profile_id or tts_voice or str(settings.tts_default_voice or "中文女").strip(),
            tts_speed=float(payload.get("tts_speed", settings.tts_speed_default) or settings.tts_speed_default),
            keep_original_audio=bool(
                payload.get(
                    "keep_original_audio",
                    settings.tts_keep_original_audio_default,
                )
            ),
            uploaded_voiceover_path=self._resolve_uploaded_voiceover_path(
                str(payload.get("uploaded_voiceover_path", "") or "")
            ),
            uploaded_voiceover_duration_ms=max(
                0,
                int(payload.get("uploaded_voiceover_duration_ms", 0) or 0),
            ),
            source_path=source_path,
            source_hash=str(task.get("source_hash", "") or ""),
            source_size=int(task.get("source_size", 0) or 0),
            output_path=settings.output_dir / f"{output_base}_cut.mp4",
            subtitle_work_path=settings.output_dir / f"{output_base}_cut_nosubs.mp4",
            raw_output_path=settings.output_dir / f"{output_base}_cut_raw.mp4",
            srt_path=settings.output_dir / f"{output_base}.srt",
            ass_path=settings.output_dir / f"{output_base}.ass",
            edl_path=settings.output_dir / f"{output_base}.edl",
            voiceover_path=settings.voiceover_dir / f"{output_base}_voice.wav",
        )

    def _resolve_uploaded_voiceover_path(self, relative_path: str) -> Path:
        normalized = str(relative_path or "").replace("\\", "/").strip("/")
        if not normalized or normalized.startswith("../") or "/../" in normalized:
            return Path()
        base_dir = settings.voiceover_dir.resolve()
        candidate = (settings.voiceover_dir / normalized).resolve()
        try:
            candidate.relative_to(base_dir)
        except ValueError:
            return Path()
        return candidate


task_run_context_service = TaskRunContextService()
