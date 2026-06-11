from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable

from app.core.config import settings
from app.domain.schemas import build_script_from_beats, normalize_draft_beats
from app.services.alignment_workflow_service import alignment_workflow_service
from app.services.asr_workflow_service import asr_workflow_service
from app.services.draft_workflow_service import draft_workflow_service
from app.services.media_service import media_service
from app.services.task_draft_phase_service import task_draft_phase_service
from app.services.task_finalize_output_service import task_finalize_output_service
from app.services.task_finalize_plan_models import FinalizePlanningResult
from app.services.task_finalize_plan_validation_service import task_finalize_plan_validation_service
from app.services.task_run_context_service import TaskRunContext
from app.services.task_state_service import task_state_service
from app.services.task_store_service import task_store_service
from app.services.voice_workflow_service import voice_workflow_service
from app.workflows import workflow_registry
from app.workflows.runtime import WorkflowNodeRegistry, WorkflowRuntime, WorkflowRuntimeContext


def _voiceover_base_dir() -> Path:
    return settings.voiceover_dir.resolve()


def _voiceover_relative_audio_path(audio_path: Any) -> str:
    raw = str(audio_path or "").strip()
    if not raw:
        return ""
    path = Path(raw)
    candidate = path.resolve() if path.is_absolute() else (_voiceover_base_dir() / raw).resolve()
    try:
        relative = candidate.relative_to(_voiceover_base_dir())
    except ValueError:
        return ""
    return relative.as_posix()


def _resolve_voiceover_audio_path(audio_path: Any) -> Path:
    raw = str(audio_path or "").strip()
    if not raw:
        return Path()
    path = Path(raw)
    candidate = path.resolve() if path.is_absolute() else (_voiceover_base_dir() / raw).resolve()
    try:
        candidate.relative_to(_voiceover_base_dir())
    except ValueError:
        return Path()
    return candidate


def _synthesized_beats_for_result(beats: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    payload: list[Dict[str, Any]] = []
    for index, item in enumerate(beats or [], start=1):
        text = str(item.get("text", "") or "").strip()
        if not text:
            continue
        audio_path = _voiceover_relative_audio_path(item.get("audio_path", ""))
        payload_item: Dict[str, Any] = {
            "id": str(item.get("id", "") or f"beat_{index}"),
            "title": str(item.get("title", "") or f"第 {index} 段"),
            "text": text,
            "order": int(item.get("order", index) or index),
            "voice_duration_ms": max(0, int(item.get("voice_duration_ms", 0) or 0)),
        }
        if audio_path:
            payload_item["audio_path"] = audio_path
        payload.append(payload_item)
    return payload


def _load_synthesized_beats_from_result(
    *,
    task_id: str,
    result: Dict[str, Any],
    reviewed_beats: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    raw_items = result.get("synthesized_beats", []) or []
    if not isinstance(raw_items, list) or len(raw_items) != len(reviewed_beats):
        return []

    loaded: list[Dict[str, Any]] = []
    for index, (reviewed, raw_item) in enumerate(zip(reviewed_beats, raw_items), start=1):
        if not isinstance(raw_item, dict):
            return []
        audio_path = _resolve_voiceover_audio_path(raw_item.get("audio_path", ""))
        if not audio_path.is_file():
            return []
        duration_ms = max(
            0,
            int(
                raw_item.get("voice_duration_ms")
                or reviewed.get("voice_duration_ms")
                or media_service.probe_duration_ms(str(audio_path))
                or 0
            ),
        )
        if duration_ms <= 0:
            return []
        loaded.append(
            {
                "id": str(reviewed.get("id", "") or raw_item.get("id", "") or f"beat_{index}"),
                "title": str(reviewed.get("title", "") or raw_item.get("title", "") or f"第 {index} 段"),
                "text": str(reviewed.get("text", "") or raw_item.get("text", "") or "").strip(),
                "order": int(reviewed.get("order", raw_item.get("order", index)) or index),
                "voice_duration_ms": duration_ms,
                "audio_path": audio_path,
            }
        )
    return loaded


def _recover_synthesized_beats_from_files(
    *,
    task_id: str,
    voice_source: str,
    reviewed_beats: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    task_dir = _voiceover_base_dir() / task_id
    if not task_dir.is_dir():
        return []
    prefix = "uploaded_beat" if voice_source == "uploaded_voiceover" else "draft_beat"
    recovered: list[Dict[str, Any]] = []
    for index, beat in enumerate(reviewed_beats):
        audio_path = (task_dir / f"{prefix}_{index:02d}.wav").resolve()
        try:
            audio_path.relative_to(_voiceover_base_dir())
        except ValueError:
            return []
        if not audio_path.is_file():
            return []
        duration_ms = max(
            0,
            int(beat.get("voice_duration_ms", 0) or media_service.probe_duration_ms(str(audio_path)) or 0),
        )
        if duration_ms <= 0:
            return []
        recovered.append(
            {
                **beat,
                "voice_duration_ms": duration_ms,
                "audio_path": audio_path,
            }
        )
    return recovered


class PrepareTaskNode:
    node_type = "prepare_task"
    title = "准备任务上下文"

    def run(self, context: WorkflowRuntimeContext) -> None:
        is_draft = context.phase == "draft"
        is_retry_alignment = context.phase == "retry_alignment"
        context.update_task(
            context.task_id,
            status="running",
            stage="preparing_alignment_retry" if is_retry_alignment else "preparing",
            progress=5 if is_draft else (84 if is_retry_alignment else 74),
            message=(
                "正在准备任务上下文"
                if is_draft
                else (
                    "正在准备从配音完成后重新选片"
                    if is_retry_alignment
                    else "正在准备继续处理已确认文案"
                )
            ),
            error="",
        )


class ASRTranscribeNode:
    node_type = "asr_transcribe"
    title = "ASR 识别"

    def run(self, context: WorkflowRuntimeContext) -> None:
        run_context = context.run_context
        context.data["asr_result"] = asr_workflow_service.load_or_build_asr(
            task_id=context.task_id,
            source_path=run_context.source_path,
            source_hash=run_context.source_hash,
            source_size=run_context.source_size,
            original_filename=run_context.original_filename,
            update_task=context.update_task,
            record_task_event=context.record_task_event,
        )


class DraftPhaseNode:
    node_type = "draft_phase"
    title = "生成文案初稿"

    def run(self, context: WorkflowRuntimeContext) -> None:
        asr_result = context.data.get("asr_result")
        if asr_result is None:
            raise RuntimeError("ASR result is missing before draft phase")
        task_draft_phase_service.run_draft(
            context=context.run_context,
            subtitles=asr_result.subtitles,
            audio_path=asr_result.audio_path,
            asr_cache_hit=asr_result.cache_hit,
            update_task=context.update_task,
        )


class ScriptToBeatsNode:
    node_type = "script_to_beats"
    title = "定稿文案拆分"

    def run(self, context: WorkflowRuntimeContext) -> None:
        asr_result = context.data.get("asr_result")
        if asr_result is None:
            raise RuntimeError("ASR result is missing before script split")
        draft = draft_workflow_service.build_script_match_draft(
            script=context.run_context.request_text,
        )
        context.update_task(
            context.task_id,
            status="waiting_review",
            stage="awaiting_script_review",
            progress=68,
            message="定稿文案已拆分，请确认后继续匹配素材",
            artifacts={"audio_url": f"/audio/{asr_result.audio_path.name}"},
            result={
                "subtitle_count": len(asr_result.subtitles),
                "asr_cache_hit": asr_result.cache_hit,
                "draft_script": draft.script,
                "draft_beats": draft.beats,
                "grounding": draft.grounding,
                "suggestions": draft.suggestions,
                "review_status": "awaiting_review",
                "voiceover_enabled": context.run_context.enable_dubbing,
                "voiceover_script": draft.voiceover_script,
                "draft_strategy": "script_to_beats",
            },
        )


class VoicePlanNode:
    node_type = "voice_plan"
    title = "配音/时长准备"

    def run(self, context: WorkflowRuntimeContext) -> None:
        asr_result = context.data.get("asr_result")
        if asr_result is None:
            raise RuntimeError("ASR result is missing before voice planning")
        run_context = context.run_context
        current_task = task_store_service.get_task(context.task_id)
        current_result = (current_task.get("result", {}) if current_task else {}) or {}
        reviewed_beats = normalize_draft_beats(current_result.get("draft_beats", []))
        if not reviewed_beats:
            raise RuntimeError("文案草稿为空，请先确认文案内容。")

        context.data["suggestions"] = current_result.get("suggestions", []) or []

        if run_context.enable_dubbing:
            voice_source_label = (
                "上传完整配音"
                if run_context.voice_source == "uploaded_voiceover"
                else run_context.voice_mode
            )
            context.update_task(
                context.task_id,
                stage="synthesizing_voice",
                progress=80,
                message=f"正在根据确认后的文案准备配音（{len(reviewed_beats)} 段，{voice_source_label}）",
                artifacts={"audio_url": f"/audio/{asr_result.audio_path.name}"},
                result={
                    "subtitle_count": len(asr_result.subtitles),
                    "asr_cache_hit": asr_result.cache_hit,
                    "review_status": "approved",
                    "voice_source": run_context.voice_source,
                    "voiceover_segment_count": len(reviewed_beats),
                },
            )
            if run_context.voice_source == "uploaded_voiceover":
                synthesized_beats = voice_workflow_service.split_uploaded_voiceover_beats(
                    task_id=context.task_id,
                    uploaded_voiceover_path=run_context.uploaded_voiceover_path,
                    uploaded_voiceover_duration_ms=run_context.uploaded_voiceover_duration_ms,
                    beats=reviewed_beats,
                    update_task=context.update_task,
                )
            else:
                synthesized_beats = voice_workflow_service.synthesize_reviewed_beats(
                    task_id=context.task_id,
                    voice_mode=run_context.voice_mode,
                    voice=run_context.voice_profile_ref,
                    beats=reviewed_beats,
                    speed=run_context.tts_speed,
                    user_id=run_context.user_id,
                    update_task=context.update_task,
                )
            if not synthesized_beats:
                raise RuntimeError("没有生成有效配音，请检查文案内容或配音配置。")

            reviewed_beats = normalize_draft_beats(synthesized_beats)
            approved_script = build_script_from_beats(reviewed_beats)
            context.update_task(
                context.task_id,
                stage="planning_from_voice",
                progress=86,
                message="已拿到真实配音时长，正在按语音时长选择视频片段",
                result={
                    "draft_script": approved_script,
                    "draft_beats": reviewed_beats,
                    "synthesized_beats": _synthesized_beats_for_result(synthesized_beats),
                    "voiceover_script": approved_script,
                    "voiceover_segment_count": len(reviewed_beats),
                },
            )
            context.data["reviewed_beats"] = reviewed_beats
            context.data["synthesized_beats"] = synthesized_beats
            context.data["approved_script"] = approved_script
            return

        reviewed_beats = task_finalize_plan_validation_service.attach_estimated_beat_durations(
            reviewed_beats,
            duration_seconds=run_context.duration_seconds,
        )
        approved_script = build_script_from_beats(reviewed_beats)
        context.update_task(
            context.task_id,
            stage="planning",
            progress=82,
            message="文案已确认，正在按 beat 全量字幕选片",
            artifacts={"audio_url": f"/audio/{asr_result.audio_path.name}"},
            result={
                "subtitle_count": len(asr_result.subtitles),
                "asr_cache_hit": asr_result.cache_hit,
                "review_status": "approved",
                "draft_script": approved_script,
                "draft_beats": reviewed_beats,
            },
        )
        context.data["reviewed_beats"] = reviewed_beats
        context.data["synthesized_beats"] = []
        context.data["approved_script"] = approved_script


class LoadVoicePlanNode:
    node_type = "load_voice_plan"
    title = "恢复配音/时长结果"

    def run(self, context: WorkflowRuntimeContext) -> None:
        asr_result = context.data.get("asr_result")
        if asr_result is None:
            raise RuntimeError("ASR result is missing before voice plan recovery")
        run_context = context.run_context
        current_task = task_store_service.get_task(context.task_id)
        current_result = (current_task.get("result", {}) if current_task else {}) or {}
        reviewed_beats = normalize_draft_beats(current_result.get("draft_beats", []))
        if not reviewed_beats:
            raise RuntimeError("没有可恢复的已确认文案，请回到文案确认步骤后再继续。")

        context.data["suggestions"] = current_result.get("suggestions", []) or []

        if run_context.enable_dubbing:
            synthesized_beats = _load_synthesized_beats_from_result(
                task_id=context.task_id,
                result=current_result,
                reviewed_beats=reviewed_beats,
            )
            if not synthesized_beats:
                synthesized_beats = _recover_synthesized_beats_from_files(
                    task_id=context.task_id,
                    voice_source=run_context.voice_source,
                    reviewed_beats=reviewed_beats,
                )
            if not synthesized_beats:
                raise RuntimeError("没有找到已完成的配音分段，请重新确认文案以生成配音后再选片。")

            reviewed_beats = normalize_draft_beats(synthesized_beats)
            approved_script = build_script_from_beats(reviewed_beats)
            context.update_task(
                context.task_id,
                stage="planning_from_voice",
                progress=86,
                message="配音已完成，正在重新请求大模型选片",
                artifacts={"audio_url": f"/audio/{asr_result.audio_path.name}"},
                result={
                    "review_status": "approved",
                    "draft_script": approved_script,
                    "draft_beats": reviewed_beats,
                    "synthesized_beats": _synthesized_beats_for_result(synthesized_beats),
                    "voiceover_script": approved_script,
                    "voiceover_segment_count": len(reviewed_beats),
                    "matched_segments": [],
                    "segment_count": 0,
                    "selection_strategy": "",
                    "total_duration_ms": 0,
                    "clip_plan_id": "",
                },
            )
            context.data["reviewed_beats"] = reviewed_beats
            context.data["synthesized_beats"] = synthesized_beats
            context.data["approved_script"] = approved_script
            return

        reviewed_beats = task_finalize_plan_validation_service.attach_estimated_beat_durations(
            reviewed_beats,
            duration_seconds=run_context.duration_seconds,
        )
        approved_script = build_script_from_beats(reviewed_beats)
        context.update_task(
            context.task_id,
            stage="planning",
            progress=82,
            message="正在重新请求大模型选片",
            artifacts={"audio_url": f"/audio/{asr_result.audio_path.name}"},
            result={
                "review_status": "approved",
                "draft_script": approved_script,
                "draft_beats": reviewed_beats,
                "matched_segments": [],
                "segment_count": 0,
                "selection_strategy": "",
                "total_duration_ms": 0,
                "clip_plan_id": "",
            },
        )
        context.data["reviewed_beats"] = reviewed_beats
        context.data["synthesized_beats"] = []
        context.data["approved_script"] = approved_script


class AlignPlanNode:
    node_type = "align_plan"
    title = "文案匹配画面"

    def run(self, context: WorkflowRuntimeContext) -> None:
        asr_result = context.data.get("asr_result")
        if asr_result is None:
            raise RuntimeError("ASR result is missing before alignment")
        run_context = context.run_context
        reviewed_beats = list(context.data.get("reviewed_beats", []) or [])
        synthesized_beats = list(context.data.get("synthesized_beats", []) or [])
        if not reviewed_beats:
            raise RuntimeError("Reviewed beats are missing before alignment")

        if run_context.enable_dubbing:
            alignment_plan = alignment_workflow_service.plan_segments_with_global_llm(
                task_id=context.task_id,
                beats=synthesized_beats,
                synthesized_beats=synthesized_beats,
                subtitles=asr_result.subtitles,
                style=run_context.style,
                project_context=run_context.project_context,
                record_task_event=context.record_task_event,
            )
            reviewed_beats = alignment_plan.beats_payload()
            synthesized_beats = alignment_plan.synthesized_beats_payload()
            source_segments = alignment_plan.source_segments_payload()
            task_finalize_plan_validation_service.validate_segment_count(
                reviewed_beats=reviewed_beats,
                source_segments=source_segments,
            )
            total_duration_ms = task_finalize_plan_validation_service.total_segment_duration_ms(source_segments)
            task_finalize_plan_validation_service.validate_voice_duration_coverage(
                reviewed_beats=reviewed_beats,
                source_segments=source_segments,
                total_duration_ms=total_duration_ms,
            )
            alignment_workflow_service.validate_voice_aligned_segments(reviewed_beats, source_segments)
        else:
            alignment_plan = alignment_workflow_service.plan_segments_with_global_llm(
                task_id=context.task_id,
                beats=reviewed_beats,
                subtitles=asr_result.subtitles,
                style=run_context.style,
                project_context=run_context.project_context,
                record_task_event=context.record_task_event,
            )
            reviewed_beats = alignment_plan.beats_payload()
            source_segments = alignment_plan.source_segments_payload()
            task_finalize_plan_validation_service.validate_segment_count(
                reviewed_beats=reviewed_beats,
                source_segments=source_segments,
            )
            total_duration_ms = task_finalize_plan_validation_service.total_segment_duration_ms(source_segments)
            alignment_workflow_service.validate_voice_aligned_segments(reviewed_beats, source_segments)

        approved_script = build_script_from_beats(reviewed_beats)
        context.data["finalize_plan"] = FinalizePlanningResult(
            reviewed_beats=reviewed_beats,
            synthesized_beats=synthesized_beats,
            source_segments=source_segments,
            approved_script=approved_script,
            selection_strategy=alignment_plan.selection_strategy,
            total_duration_ms=total_duration_ms,
        )


class RenderOutputNode:
    node_type = "render_output"
    title = "渲染导出"

    def run(self, context: WorkflowRuntimeContext) -> None:
        asr_result = context.data.get("asr_result")
        if asr_result is None:
            raise RuntimeError("ASR result is missing before render")
        plan = context.data.get("finalize_plan")
        if plan is None:
            raise RuntimeError("Finalize plan is missing before render")
        current_task = task_store_service.get_task(context.task_id)
        current_result = (current_task.get("result", {}) if current_task else {}) or {}
        suggestions = context.data.get("suggestions")
        if suggestions is None:
            suggestions = current_result.get("suggestions", []) or []
        task_finalize_output_service.render_output(
            context=context.run_context,
            subtitles=asr_result.subtitles,
            suggestions=suggestions,
            plan=plan,
            update_task=context.update_task,
            record_task_event=context.record_task_event,
        )


class TaskWorkflowRuntimeService:
    DEFAULT_PHASE_SEQUENCES: Dict[str, list[str]] = {
        "draft": ["prepare_task", "asr_transcribe", "draft_phase"],
        "finalize": ["prepare_task", "asr_transcribe", "voice_plan", "align_plan", "render_output"],
        "retry_alignment": ["prepare_task", "asr_transcribe", "load_voice_plan", "align_plan", "render_output"],
    }

    def __init__(self) -> None:
        registry = WorkflowNodeRegistry()
        registry.register(PrepareTaskNode())
        registry.register(ASRTranscribeNode())
        registry.register(DraftPhaseNode())
        registry.register(ScriptToBeatsNode())
        registry.register(VoicePlanNode())
        registry.register(LoadVoicePlanNode())
        registry.register(AlignPlanNode())
        registry.register(RenderOutputNode())
        self._runtime = WorkflowRuntime(
            registry=registry,
            phase_sequences=self.DEFAULT_PHASE_SEQUENCES,
        )

    def _phase_sequences_from_template(self, template: Any) -> tuple[Dict[str, Iterable[str]], str]:
        if template is None:
            return {}, "default"
        runtime = getattr(template, "runtime", None) or {}
        if not isinstance(runtime, dict):
            return {}, "default"
        raw_sequences = runtime.get("phase_sequences", {})
        if not isinstance(raw_sequences, dict):
            return {}, "default"

        phase_sequences: Dict[str, list[str]] = {}
        for phase, node_types in raw_sequences.items():
            normalized_phase = str(phase or "").strip()
            if not normalized_phase or not isinstance(node_types, list):
                continue
            normalized_nodes = [
                str(node_type or "").strip()
                for node_type in node_types
                if str(node_type or "").strip()
            ]
            if normalized_nodes:
                phase_sequences[normalized_phase] = normalized_nodes
        if not phase_sequences:
            return {}, "default"
        return phase_sequences, "template"

    def run(
        self,
        *,
        task: Dict[str, Any],
        run_context: TaskRunContext,
        phase: str,
    ) -> None:
        payload = dict(task.get("payload", {}) or {})
        pipeline_mode = workflow_registry.normalize_template_id(str(payload.get("pipeline_mode", "") or ""))
        template = workflow_registry.get_template(pipeline_mode)
        phase_sequences, sequence_source = self._phase_sequences_from_template(template)
        runtime_context = WorkflowRuntimeContext(
            task_id=run_context.task_id,
            phase=str(phase or "draft"),
            task=task,
            run_context=run_context,
            pipeline_mode=pipeline_mode,
            template_title=str(payload.get("workflow_template_title", "") or (template.title if template else "")),
            update_task=task_state_service.update_task,
            record_task_event=task_state_service.record_task_event,
        )
        self._runtime.run(
            runtime_context,
            phase_sequences=phase_sequences,
            sequence_source=sequence_source,
        )


task_workflow_runtime_service = TaskWorkflowRuntimeService()
