from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class DraftBeat(BaseModel):
    id: str = ""
    title: str = ""
    text: str = ""
    order: int = 0
    voice_duration_ms: int = 0

    @classmethod
    def from_raw(cls, item: Any, index: int) -> "DraftBeat | None":
        if isinstance(item, str):
            raw: Dict[str, Any] = {}
            text = item.strip()
        elif isinstance(item, dict):
            raw = dict(item or {})
            text = str(raw.get("text", "") or "").strip()
        else:
            return None

        if not text:
            return None

        return cls(
            id=str(raw.get("id", "") or f"beat_{index}"),
            title=str(raw.get("title", "") or f"第 {index} 段"),
            text=text,
            order=int(raw.get("order", index) or index),
            voice_duration_ms=max(0, int(raw.get("voice_duration_ms", 0) or 0)),
        )

    def to_payload(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "text": self.text,
            "order": self.order,
            "voice_duration_ms": self.voice_duration_ms,
        }


class SynthesizedBeat(DraftBeat):
    audio_path: Any = ""

    @classmethod
    def from_raw(cls, item: Any, index: int) -> "SynthesizedBeat | None":
        if isinstance(item, str):
            raw: Dict[str, Any] = {}
            text = item.strip()
        elif isinstance(item, dict):
            raw = dict(item or {})
            text = str(raw.get("text", "") or "").strip()
        else:
            return None

        if not text:
            return None

        return cls(
            id=str(raw.get("id", "") or f"beat_{index}"),
            title=str(raw.get("title", "") or f"第 {index} 段"),
            text=text,
            order=int(raw.get("order", index) or index),
            voice_duration_ms=max(0, int(raw.get("voice_duration_ms", 0) or 0)),
            audio_path=raw.get("audio_path", ""),
        )

    def to_payload(self, *, include_audio_path: bool = True) -> Dict[str, Any]:
        payload = super().to_payload()
        if include_audio_path and self.audio_path:
            payload["audio_path"] = self.audio_path
        return payload


class SubtitleUnit(BaseModel):
    start: int = 0
    end: int = 0
    text: str = ""

    @classmethod
    def from_raw(cls, item: Any) -> "SubtitleUnit | None":
        if not isinstance(item, dict):
            return None
        try:
            start = int(item.get("start", 0) or 0)
            end = int(item.get("end", 0) or 0)
        except Exception:
            return None
        text = str(item.get("text", "") or "").strip()
        if not text or end <= start:
            return None
        return cls(start=start, end=end, text=text)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "start": max(0, int(self.start or 0)),
            "end": max(0, int(self.end or 0)),
            "text": self.text.strip(),
        }


class AlignedSegment(BaseModel):
    start: int = 0
    end: int = 0
    content: str = ""
    dubbing: str = ""
    voice_duration_ms: int = 0
    semantic_start: int = 0
    semantic_end: int = 0
    duration_fit_adjusted: bool = False
    duration_fit_original_start: int = 0
    duration_fit_original_end: int = 0

    @classmethod
    def from_raw(cls, item: Any) -> "AlignedSegment | None":
        if not isinstance(item, dict):
            return None
        try:
            start = int(item.get("start", 0) or 0)
            end = int(item.get("end", 0) or 0)
        except Exception:
            return None
        if end <= start:
            return None
        return cls(
            start=start,
            end=end,
            content=str(item.get("content", "") or "").strip(),
            dubbing=str(item.get("dubbing", "") or "").strip(),
            voice_duration_ms=max(0, int(item.get("voice_duration_ms", 0) or 0)),
            semantic_start=max(0, int(item.get("semantic_start", 0) or 0)),
            semantic_end=max(0, int(item.get("semantic_end", 0) or 0)),
            duration_fit_adjusted=bool(item.get("duration_fit_adjusted", False)),
            duration_fit_original_start=max(0, int(item.get("duration_fit_original_start", 0) or 0)),
            duration_fit_original_end=max(0, int(item.get("duration_fit_original_end", 0) or 0)),
        )

    def to_payload(self) -> Dict[str, Any]:
        payload = {
            "start": max(0, int(self.start or 0)),
            "end": max(0, int(self.end or 0)),
            "content": self.content.strip(),
            "voice_duration_ms": max(0, int(self.voice_duration_ms or 0)),
        }
        if self.dubbing.strip():
            payload["dubbing"] = self.dubbing.strip()
        if self.semantic_start or self.semantic_end:
            payload["semantic_start"] = max(0, int(self.semantic_start or 0))
            payload["semantic_end"] = max(0, int(self.semantic_end or 0))
        if self.duration_fit_adjusted:
            payload["duration_fit_adjusted"] = True
            payload["duration_fit_original_start"] = max(0, int(self.duration_fit_original_start or 0))
            payload["duration_fit_original_end"] = max(0, int(self.duration_fit_original_end or 0))
        return payload


class AlignmentPlan(BaseModel):
    beats: List[DraftBeat] = Field(default_factory=list)
    synthesized_beats: List[SynthesizedBeat] = Field(default_factory=list)
    source_segments: List[AlignedSegment] = Field(default_factory=list)
    selection_strategy: str = "none"

    @classmethod
    def from_raw(
        cls,
        *,
        beats: List[Dict[str, Any]] | None = None,
        synthesized_beats: List[Dict[str, Any]] | None = None,
        source_segments: List[Dict[str, Any]] | None = None,
        selection_strategy: str = "none",
    ) -> "AlignmentPlan":
        normalized_beats = [
            beat
            for index, item in enumerate(beats or [], start=1)
            if (beat := DraftBeat.from_raw(item, index)) is not None
        ]
        normalized_synthesized = [
            beat
            for index, item in enumerate(synthesized_beats or [], start=1)
            if (beat := SynthesizedBeat.from_raw(item, index)) is not None
        ]
        normalized_segments = [
            segment
            for item in source_segments or []
            if (segment := AlignedSegment.from_raw(item)) is not None
        ]
        return cls(
            beats=normalized_beats,
            synthesized_beats=normalized_synthesized,
            source_segments=normalized_segments,
            selection_strategy=str(selection_strategy or "none"),
        )

    @classmethod
    def empty(
        cls,
        *,
        beats: List[Dict[str, Any]] | None = None,
        synthesized_beats: List[Dict[str, Any]] | None = None,
    ) -> "AlignmentPlan":
        return cls.from_raw(
            beats=beats or [],
            synthesized_beats=synthesized_beats or [],
            source_segments=[],
            selection_strategy="none",
        )

    def beats_payload(self) -> List[Dict[str, Any]]:
        return [beat.to_payload() for beat in self.beats]

    def synthesized_beats_payload(self, *, include_audio_path: bool = True) -> List[Dict[str, Any]]:
        return [
            beat.to_payload(include_audio_path=include_audio_path)
            for beat in self.synthesized_beats
        ]

    def source_segments_payload(self) -> List[Dict[str, Any]]:
        return [segment.to_payload() for segment in self.source_segments]

    def to_payload(self, *, include_audio_path: bool = True) -> Dict[str, Any]:
        return {
            "beats": self.beats_payload(),
            "synthesized_beats": self.synthesized_beats_payload(include_audio_path=include_audio_path),
            "source_segments": self.source_segments_payload(),
            "selection_strategy": self.selection_strategy,
        }


class TaskEvent(BaseModel):
    id: int = 0
    task_id: str = ""
    event_type: str = "state_changed"
    status: str = ""
    stage: str = ""
    progress: int = 0
    message: str = ""
    detail: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""


class ProjectKnowledgeUpdate(BaseModel):
    title: str = "项目知识库"
    content: str = ""
    project_id: str = "default"


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    default_knowledge_base_id: str | None = None
    default_pipeline_mode: str | None = None
    default_knowledge_policy: str | None = None
    default_duration_seconds: int | None = None
    default_style: str | None = None
    default_enable_dubbing: bool | None = None
    default_voice_mode: str | None = None
    default_voice_profile_id: str | None = None
    default_tts_speed: float | None = None
    default_keep_original_audio: bool | None = None


class AuthCredentials(BaseModel):
    username: str = ""
    password: str = ""
    display_name: str = ""


class TaskPayload(BaseModel):
    original_filename: str = ""
    request_text: str = ""
    request_mode: str = "requirements"
    project_id: str = "default"
    project_title: str = "默认项目"
    project_default_knowledge_base_id: str = ""
    pipeline_mode: str = "narration_clip"
    workflow_template_title: str = ""
    knowledge_policy: str = "none"
    knowledge_used: bool = False
    project_context: str = ""
    project_context_extra: str = ""
    knowledge_base_id: str = ""
    knowledge_base_title: str = ""
    knowledge_base_context: str = ""
    knowledge_base_updated_at: str = ""
    duration_seconds: int = 0
    style: str = "summary"
    enable_dubbing: bool = False
    voice_source: str = "tts"
    voice_mode: str = "standard"
    voice_profile_id: str = ""
    voice_profile_label: str = ""
    tts_voice: str = ""
    tts_speed: float = 1.0
    keep_original_audio: bool = True
    uploaded_voiceover_path: str = ""
    uploaded_voiceover_name: str = ""
    uploaded_voiceover_duration_ms: int = 0

    def to_payload(self) -> Dict[str, Any]:
        return {
            "original_filename": self.original_filename,
            "request_text": self.request_text,
            "request_mode": self.request_mode,
            "project_id": self.project_id,
            "project_title": self.project_title,
            "project_default_knowledge_base_id": self.project_default_knowledge_base_id,
            "pipeline_mode": self.pipeline_mode,
            "workflow_template_title": self.workflow_template_title,
            "knowledge_policy": self.knowledge_policy,
            "knowledge_used": self.knowledge_used,
            "project_context": self.project_context,
            "project_context_extra": self.project_context_extra,
            "knowledge_base_id": self.knowledge_base_id,
            "knowledge_base_title": self.knowledge_base_title,
            "knowledge_base_context": self.knowledge_base_context,
            "knowledge_base_updated_at": self.knowledge_base_updated_at,
            "duration_seconds": self.duration_seconds,
            "style": self.style,
            "enable_dubbing": self.enable_dubbing,
            "voice_source": self.voice_source,
            "voice_mode": self.voice_mode,
            "voice_profile_id": self.voice_profile_id,
            "voice_profile_label": self.voice_profile_label,
            "tts_voice": self.tts_voice,
            "tts_speed": self.tts_speed,
            "keep_original_audio": self.keep_original_audio,
            "uploaded_voiceover_path": self.uploaded_voiceover_path,
            "uploaded_voiceover_name": self.uploaded_voiceover_name,
            "uploaded_voiceover_duration_ms": self.uploaded_voiceover_duration_ms,
        }


class TaskArtifacts(BaseModel):
    source_video_url: str = ""
    output_video_url: str = ""
    srt_url: str = ""
    edl_url: str = ""
    audio_url: str = ""
    voiceover_audio_url: str = ""
    uploaded_voiceover_url: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "source_video_url": self.source_video_url,
            "output_video_url": self.output_video_url,
            "srt_url": self.srt_url,
            "edl_url": self.edl_url,
            "audio_url": self.audio_url,
            "voiceover_audio_url": self.voiceover_audio_url,
            "uploaded_voiceover_url": self.uploaded_voiceover_url,
        }


class TaskResult(BaseModel):
    subtitle_count: int = 0
    segment_count: int = 0
    matched_segments: List[Dict[str, Any]] = Field(default_factory=list)
    draft_script: str = ""
    draft_beats: List[Dict[str, Any]] = Field(default_factory=list)
    grounding: Dict[str, Any] = Field(default_factory=dict)
    review_status: str = "pending_generation"
    script: str = ""
    suggestions: List[Any] = Field(default_factory=list)
    plan_mode: str = ""
    selection_strategy: str = ""
    asr_cache_hit: bool = False
    total_duration_ms: int = 0
    clip_plan_id: str = ""
    voiceover_enabled: bool = False
    voiceover_script: str = ""
    voiceover_segment_count: int = 0

    def to_payload(self) -> Dict[str, Any]:
        return {
            "subtitle_count": self.subtitle_count,
            "segment_count": self.segment_count,
            "matched_segments": self.matched_segments,
            "draft_script": self.draft_script,
            "draft_beats": self.draft_beats,
            "grounding": self.grounding,
            "review_status": self.review_status,
            "script": self.script,
            "suggestions": self.suggestions,
            "plan_mode": self.plan_mode,
            "selection_strategy": self.selection_strategy,
            "asr_cache_hit": self.asr_cache_hit,
            "total_duration_ms": self.total_duration_ms,
            "clip_plan_id": self.clip_plan_id,
            "voiceover_enabled": self.voiceover_enabled,
            "voiceover_script": self.voiceover_script,
            "voiceover_segment_count": self.voiceover_segment_count,
        }


class TaskRecord(BaseModel):
    id: str
    user_id: str = "local"
    status: str = "queued"
    progress: int = 0
    stage: str = "queued"
    message: str = ""
    created_at: str = ""
    updated_at: str = ""
    project_id: str = "default"
    payload: TaskPayload
    artifacts: TaskArtifacts
    result: TaskResult
    error: str = ""
    source_path: str = ""
    source_hash: str = ""
    source_size: int = 0

    def to_payload(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "progress": self.progress,
            "stage": self.stage,
            "message": self.message,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "project_id": self.project_id,
            "payload": self.payload.to_payload(),
            "artifacts": self.artifacts.to_payload(),
            "result": self.result.to_payload(),
            "error": self.error,
            "source_path": self.source_path,
            "source_hash": self.source_hash,
            "source_size": self.source_size,
        }


def normalize_draft_beats(beats: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(beats or [], start=1):
        beat = DraftBeat.from_raw(item, index)
        if beat is not None:
            normalized.append(beat.to_payload())
    return normalized


def build_script_from_beats(beats: List[Dict[str, Any]]) -> str:
    lines = [
        str(item.get("text", "") or "").strip()
        for item in beats or []
        if str(item.get("text", "") or "").strip()
    ]
    return "\n".join(lines)
