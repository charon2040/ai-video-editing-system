from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from fastapi import HTTPException

from app.core.config import settings
from app.workflows import workflow_registry


@dataclass(frozen=True)
class TaskRequestOptions:
    request_text: str
    request_mode: str
    project_id: str
    pipeline_mode: str
    project_context: str
    knowledge_policy: str
    knowledge_base_id: str
    duration_seconds: int
    style: str
    enable_dubbing: bool
    voice_source: str
    voice_mode: str
    voice_profile_id: str
    tts_voice: str
    tts_speed: float
    keep_original_audio: bool


def normalize_request_mode(requirements: str, target_script: str) -> tuple[str, str]:
    request_text = requirements.strip() or target_script.strip()
    if not request_text:
        raise HTTPException(status_code=400, detail="Missing requirements or target script")
    request_mode = "requirements" if requirements.strip() else "script"
    return request_text, request_mode


def normalize_duration_seconds(duration_seconds: int) -> int:
    value = int(duration_seconds or 0)
    return max(0, value)


def normalize_style(style: str) -> str:
    return str(style or "").strip() or "summary"


def normalize_project_context(project_context: str) -> str:
    return str(project_context or "").strip()[:12000]


def normalize_project_id(project_id: str) -> str:
    return str(project_id or "default").strip() or "default"


def normalize_pipeline_mode(pipeline_mode: str) -> str:
    value = str(pipeline_mode or "").strip()
    return workflow_registry.normalize_template_id(value) if value else ""


def normalize_knowledge_base_id(knowledge_base_id: str) -> str:
    return str(knowledge_base_id or "").strip()


def normalize_knowledge_policy(knowledge_policy: str, knowledge_base_id: str = "") -> str:
    value = str(knowledge_policy or "").strip().lower()
    if value in {"none", "project_default", "selected"}:
        return value
    return "selected" if str(knowledge_base_id or "").strip() else "none"


def normalize_bool(value: str | bool | int) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def normalize_tts_voice(tts_voice: str) -> str:
    return str(tts_voice or "").strip() or settings.tts_default_voice


def normalize_voice_mode(voice_mode: str) -> str:
    value = str(voice_mode or settings.tts_default_mode or "standard").strip().lower()
    return value if value in {"standard", "clone"} else "standard"


def normalize_voice_profile_id(voice_profile_id: str) -> str:
    return str(voice_profile_id or "").strip()


def normalize_voice_source(voice_source: str) -> str:
    value = str(voice_source or "tts").strip().lower()
    return value if value in {"tts", "uploaded_voiceover"} else "tts"


def normalize_tts_speed(tts_speed: float | str) -> float:
    try:
        value = float(tts_speed or settings.tts_speed_default)
    except Exception:
        value = float(settings.tts_speed_default)
    return max(
        float(settings.tts_speed_min),
        min(float(settings.tts_speed_max), value),
    )


def normalize_beats_json(beats_json: str) -> List[Dict[str, Any]]:
    raw = str(beats_json or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid beats_json") from exc
    if not isinstance(parsed, list):
        raise HTTPException(status_code=400, detail="beats_json must be a list")
    return [dict(item) for item in parsed if isinstance(item, dict)]


def build_create_options(
    *,
    requirements: str,
    target_script: str,
    project_id: str,
    pipeline_mode: str,
    project_context: str,
    knowledge_policy: str,
    knowledge_base_id: str,
    duration_seconds: int,
    style: str,
    enable_dubbing: str,
    voice_source: str,
    voice_mode: str,
    voice_profile_id: str,
    tts_voice: str,
    tts_speed: float,
    keep_original_audio: str,
) -> TaskRequestOptions:
    request_text, request_mode = normalize_request_mode(requirements, target_script)
    normalized_voice_source = normalize_voice_source(voice_source)
    normalized_enable_dubbing = normalize_bool(enable_dubbing) or normalized_voice_source == "uploaded_voiceover"
    return TaskRequestOptions(
        request_text=request_text,
        request_mode=request_mode,
        project_id=normalize_project_id(project_id),
        pipeline_mode=normalize_pipeline_mode(pipeline_mode),
        project_context=normalize_project_context(project_context),
        knowledge_policy=normalize_knowledge_policy(knowledge_policy, knowledge_base_id),
        knowledge_base_id=str(knowledge_base_id or "").strip(),
        duration_seconds=normalize_duration_seconds(duration_seconds),
        style=normalize_style(style),
        enable_dubbing=normalized_enable_dubbing,
        voice_source=normalized_voice_source if normalized_enable_dubbing else "tts",
        voice_mode=normalize_voice_mode(voice_mode),
        voice_profile_id=normalize_voice_profile_id(voice_profile_id),
        tts_voice=normalize_tts_voice(tts_voice),
        tts_speed=normalize_tts_speed(tts_speed),
        keep_original_audio=normalize_bool(keep_original_audio),
    )


def build_replan_options(
    *,
    base_task: Dict[str, Any],
    requirements: str,
    target_script: str,
    project_id: str,
    pipeline_mode: str,
    project_context: str,
    knowledge_policy: str,
    knowledge_base_id: str,
    duration_seconds: int,
    style: str,
    enable_dubbing: str,
    voice_source: str,
    voice_mode: str,
    voice_profile_id: str,
    tts_voice: str,
    tts_speed: str,
    keep_original_audio: str,
) -> TaskRequestOptions:
    payload = base_task.get("payload", {}) if isinstance(base_task, dict) else {}
    request_text, request_mode = normalize_request_mode(
        requirements or str(payload.get("request_text", "")),
        target_script,
    )
    explicit_knowledge_policy = bool(str(knowledge_policy or "").strip())
    explicit_knowledge_base_id = bool(str(knowledge_base_id or "").strip())
    selected_knowledge_policy = (
        normalize_knowledge_policy(knowledge_policy, knowledge_base_id)
        if explicit_knowledge_policy or explicit_knowledge_base_id
        else normalize_knowledge_policy(
            str(payload.get("knowledge_policy", "") or ""),
            str(payload.get("knowledge_base_id", "") or ""),
        )
    )
    selected_knowledge_base_id = (
        normalize_knowledge_base_id(knowledge_base_id)
        if explicit_knowledge_base_id
        else normalize_knowledge_base_id(str(payload.get("knowledge_base_id", "") or ""))
    )
    selected_project_id = (
        normalize_project_id(project_id)
        if str(project_id or "").strip()
        else normalize_project_id(str(payload.get("project_id", "") or base_task.get("project_id", "") or "default"))
    )
    selected_pipeline_mode = (
        normalize_pipeline_mode(pipeline_mode)
        if str(pipeline_mode or "").strip()
        else normalize_pipeline_mode(str(payload.get("pipeline_mode", "") or ""))
    )
    selected_voice_source = (
        normalize_voice_source(voice_source)
        if str(voice_source or "").strip()
        else normalize_voice_source(str(payload.get("voice_source", "") or "tts"))
    )
    selected_enable_dubbing = (
        normalize_bool(enable_dubbing)
        if str(enable_dubbing or "").strip()
        else bool(payload.get("enable_dubbing", False))
    ) or selected_voice_source == "uploaded_voiceover"
    return TaskRequestOptions(
        request_text=request_text,
        request_mode=request_mode,
        project_id=selected_project_id,
        pipeline_mode=selected_pipeline_mode,
        project_context=normalize_project_context(project_context),
        knowledge_policy=selected_knowledge_policy,
        knowledge_base_id=selected_knowledge_base_id,
        duration_seconds=normalize_duration_seconds(duration_seconds),
        style=normalize_style(style),
        enable_dubbing=selected_enable_dubbing,
        voice_source=selected_voice_source if selected_enable_dubbing else "tts",
        voice_mode=(
            normalize_voice_mode(voice_mode)
            if str(voice_mode or "").strip()
            else str(payload.get("voice_mode", settings.tts_default_mode) or settings.tts_default_mode)
        ),
        voice_profile_id=(
            normalize_voice_profile_id(voice_profile_id)
            if str(voice_profile_id or "").strip()
            else str(payload.get("voice_profile_id", "") or "")
        ),
        tts_voice=(
            normalize_tts_voice(tts_voice)
            if str(tts_voice or "").strip()
            else str(payload.get("tts_voice", settings.tts_default_voice) or settings.tts_default_voice)
        ),
        tts_speed=(
            normalize_tts_speed(tts_speed)
            if str(tts_speed or "").strip()
            else float(payload.get("tts_speed", settings.tts_speed_default) or settings.tts_speed_default)
        ),
        keep_original_audio=(
            normalize_bool(keep_original_audio)
            if str(keep_original_audio or "").strip()
            else bool(payload.get("keep_original_audio", settings.tts_keep_original_audio_default))
        ),
    )
