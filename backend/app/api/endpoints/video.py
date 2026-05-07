import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.asr_service import asr_service
from app.services.llm_service import llm_service
from app.services.video_service import video_service
from app.services.export_service import export_service
from app.services.advanced_render_service import advanced_render_service
from app.services.tts_service import tts_service
from app.services.editor_ai_orchestrator import editor_ai_orchestrator
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

REDUB_TTS_RATE = "+20%"

def build_output_timeline_segments(segments):
    timeline_segments = []
    current_time = 0
    for seg in segments:
        source_start = int(seg.get("start", 0))
        source_end = int(seg.get("end", 0))
        duration = max(0, source_end - source_start)
        item = dict(seg)
        item["source_start"] = source_start
        item["source_end"] = source_end
        item["start"] = current_time
        item["end"] = current_time + duration
        timeline_segments.append(item)
        current_time += duration
    return timeline_segments

def build_dubbing_script(segments):
    return "".join(
        str(seg.get("dubbing", "")).strip()
        for seg in segments
        if str(seg.get("dubbing", "")).strip()
    ).strip()

def normalize_subtitles(subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for item in subtitles or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "") or item.get("content", "") or "").strip()
        try:
            start = int(item.get("start", 0) or 0)
            end = int(item.get("end", 0) or 0)
        except Exception:
            continue
        if not text or end <= start:
            continue
        normalized.append({"text": text, "start": start, "end": end})
    normalized.sort(key=lambda seg: seg["start"])
    return normalized

def measure_redub_narration(base_name: str, narration_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return tts_service.synthesize_segments_with_duration(
        narration_segments,
        settings.OUTPUT_FOLDER,
        base_name,
        rate=REDUB_TTS_RATE,
        keep_audio=True,
    )

def bind_measured_tts_to_segments(segments: List[Dict[str, Any]], measured_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    measured_by_index: Dict[int, Dict[str, Any]] = {}
    measured_in_order: List[Dict[str, Any]] = []

    for index, item in enumerate(measured_segments or []):
        measured = dict(item or {})
        segment_index = int(measured.get("segment_index", index) or index)
        measured["segment_index"] = segment_index
        measured_by_index[segment_index] = measured
        measured_in_order.append(measured)

    bound_segments: List[Dict[str, Any]] = []
    for index, item in enumerate(segments or []):
        seg = dict(item or {})
        segment_index = int(seg.get("segment_index", index) or index)
        measured = measured_by_index.get(segment_index)
        if measured is None and index < len(measured_in_order):
            measured = measured_in_order[index]
            segment_index = int(measured.get("segment_index", segment_index) or segment_index)

        if measured is None:
            logger.warning("Missing measured TTS segment for segment_index=%s; keep model result as fallback.", segment_index)
            seg["segment_index"] = segment_index
            bound_segments.append(seg)
            continue

        real_text = str(measured.get("text", "") or measured.get("dubbing", "") or seg.get("dubbing", "")).strip()
        real_duration_ms = int(measured.get("tts_duration_ms", seg.get("required_duration_ms", 0)) or 0)

        seg["segment_index"] = segment_index
        seg["dubbing"] = real_text
        seg["tts_duration_ms"] = real_duration_ms
        seg["required_duration_ms"] = real_duration_ms
        seg["tts_probe_audio_path"] = str(measured.get("tts_probe_audio_path", "") or "")
        bound_segments.append(seg)

    return bound_segments

def extend_segment_to_duration(seg: Dict[str, Any], subtitles: List[Dict[str, Any]], min_duration_ms: int, min_gap_buffer_ms: int = 220) -> Dict[str, Any]:
    item = dict(seg)
    if not subtitles:
        return item
    required_duration_ms = max(0, int(min_duration_ms or 0)) + max(0, int(min_gap_buffer_ms or 0))
    if required_duration_ms <= 0:
        return item

    start = int(item.get("start", 0) or 0)
    end = int(item.get("end", 0) or 0)
    if end - start >= required_duration_ms:
        return item

    overlapping_indices = [
        index
        for index, sub in enumerate(subtitles)
        if not (int(sub["end"]) <= start or int(sub["start"]) >= end)
    ]
    if overlapping_indices:
        left_index = overlapping_indices[0]
        right_index = overlapping_indices[-1]
    else:
        left_index = min(range(len(subtitles)), key=lambda idx: abs(int(subtitles[idx]["start"]) - start))
        right_index = left_index
        start = min(start, int(subtitles[left_index]["start"]))
        end = max(end, int(subtitles[right_index]["end"]))

    while end - start < required_duration_ms and right_index + 1 < len(subtitles):
        right_index += 1
        end = max(end, int(subtitles[right_index]["end"]))
    while end - start < required_duration_ms and left_index - 1 >= 0:
        left_index -= 1
        start = min(start, int(subtitles[left_index]["start"]))

    merged_text = " ".join(
        str(subtitles[idx].get("text", "")).strip()
        for idx in range(left_index, right_index + 1)
        if str(subtitles[idx].get("text", "")).strip()
    ).strip()

    item["start"] = start
    item["end"] = end
    if merged_text:
        item["content"] = merged_text
    return item

def clamp_segment_to_tts_window(
    seg: Dict[str, Any],
    subtitles: List[Dict[str, Any]],
    target_duration_ms: int,
    min_gap_buffer_ms: int = 220,
    max_extra_ms: int = 1200,
) -> Dict[str, Any]:
    item = dict(seg)
    if not subtitles:
        return item

    target_duration_ms = max(0, int(target_duration_ms or 0))
    desired_min_ms = target_duration_ms + max(0, int(min_gap_buffer_ms or 0))
    desired_max_ms = max(desired_min_ms, target_duration_ms + max(0, int(max_extra_ms or 0)))
    if desired_max_ms <= 0:
        return item

    start = int(item.get("start", 0) or 0)
    end = int(item.get("end", 0) or 0)
    if end <= start:
        return item
    if end - start <= desired_max_ms:
        return item

    candidate_indices = [
        index
        for index, sub in enumerate(subtitles)
        if int(sub["start"]) < end and int(sub["end"]) > start
    ]
    if not candidate_indices:
        return item

    left_index = min(candidate_indices, key=lambda idx: abs(int(subtitles[idx]["start"]) - start))
    right_index = left_index
    new_start = min(start, int(subtitles[left_index]["start"]))
    new_end = max(start, int(subtitles[right_index]["end"]))

    while new_end - new_start < desired_min_ms and right_index + 1 < len(subtitles):
        right_index += 1
        new_end = max(new_end, int(subtitles[right_index]["end"]))

    while new_end - new_start > desired_max_ms and right_index > left_index:
        trial_end = int(subtitles[right_index - 1]["end"])
        if trial_end - new_start < desired_min_ms:
            break
        right_index -= 1
        new_end = trial_end

    merged_text = " ".join(
        str(subtitles[idx].get("text", "")).strip()
        for idx in range(left_index, right_index + 1)
        if str(subtitles[idx].get("text", "")).strip()
    ).strip()

    item["start"] = new_start
    item["end"] = new_end
    if merged_text:
        item["content"] = merged_text
    return item

def ensure_redub_segments_cover_tts(segments: List[Dict[str, Any]], subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    fixed_segments: List[Dict[str, Any]] = []
    sorted_subtitles = normalize_subtitles(subtitles)
    for index, seg in enumerate(segments or []):
        required_duration_ms = int(
            seg.get("tts_duration_ms", seg.get("required_duration_ms", 0)) or 0
        )
        fixed = clamp_segment_to_tts_window(seg, sorted_subtitles, required_duration_ms)
        fixed = extend_segment_to_duration(fixed, sorted_subtitles, required_duration_ms)
        if fixed_segments:
            prev_end = int(fixed_segments[-1].get("end", 0) or 0)
            if int(fixed.get("start", 0) or 0) < prev_end:
                fixed["start"] = prev_end
                if int(fixed.get("end", 0) or 0) <= prev_end:
                    fixed["end"] = prev_end + max(required_duration_ms, 300)
        fixed["segment_index"] = int(fixed.get("segment_index", index) or index)
        fixed_segments.append(fixed)
    return fixed_segments


@router.post("/process_video")
async def process_video(
    file: UploadFile = File(...),
    target_script: str = Form(...),
    enable_effects: bool = Form(False),
    apply_blur: bool = Form(False)
):
    """
    全链路处理：视频上传 -> 音频提取 -> ASR识别 -> LLM对齐 -> 视频剪辑与工程导出
    """
    logger.info(f"Received request to process video: {file.filename}")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    video_path = os.path.join(settings.UPLOAD_FOLDER, file.filename)
    base_name = os.path.splitext(file.filename)[0]
    audio_path = os.path.join(settings.AUDIO_FOLDER, f"{base_name}.wav")
    output_video_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}_cut.mp4")
    output_edl_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}.edl")
    timeline_source_video_path = output_video_path
    voiceover_audio_path = ""

    # 1. 保存文件
    logger.info("Step 1/6: Saving uploaded video file...")
    with open(video_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # 2. 提取音频
    logger.info("Step 2/6: Extracting audio from video...")
    if not asr_service.extract_audio_from_video(video_path, audio_path):
        logger.error("Audio extraction failed")
        raise HTTPException(status_code=500, detail="Audio extraction failed")

    # 3. 本地 ASR 识别
    logger.info("Step 3/6: Running FunASR speech recognition...")
    subtitles = asr_service.process_audio(audio_path)
    if not subtitles:
        logger.error("ASR recognition failed or returned empty")
        raise HTTPException(status_code=500, detail="ASR recognition failed or returned empty")
    logger.info(f"ASR completed. Generated {len(subtitles)} subtitle segments.")

    # 4. LLM 语义对齐 (文案匹配)
    logger.info("Step 4/6: Aligning script with subtitles using LLM...")
    cut_segments = llm_service.align_script_with_subtitles(target_script, subtitles)
    if not cut_segments:
        logger.error("LLM alignment failed")
        raise HTTPException(status_code=500, detail="LLM alignment failed")
    logger.info(f"LLM alignment completed. Identified {len(cut_segments)} segments to keep.")

    # 5. 导出 EDL 剪辑工程文件 (供 Premiere/达芬奇 导入)
    logger.info("Step 5/6: Exporting EDL project file...")
    export_service.export_to_edl(cut_segments, file.filename, output_edl_path)

    # 6. FFmpeg 本地粗剪合成 (供快速预览)
    logger.info("Step 6/6: Cutting and merging video clips...")
    if not video_service.cut_and_concat_video(video_path, output_video_path, cut_segments):
        logger.error("Video editing failed")
        raise HTTPException(status_code=500, detail="Video editing failed")
    
    final_output_path = output_video_path
    if enable_effects:
        ass_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}.ass")
        effect_output_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}_fx.mp4")

        def overlaps(a_start, a_end, b_start, b_end):
            return not (a_end <= b_start or b_end <= a_start)

        highlighted_subtitles = []
        for s in subtitles:
            is_highlight = False
            for seg in cut_segments:
                if overlaps(s["start"], s["end"], seg["start"], seg["end"]):
                    is_highlight = True
                    break
            item = dict(s)
            if is_highlight:
                item["is_highlight"] = True
            highlighted_subtitles.append(item)

        advanced_render_service.generate_ass_subtitle(
            highlighted_subtitles,
            ass_path,
            style_config={"font_size": 36}
        )

        render_commands = {"ass_file_path": ass_path}
        if apply_blur and cut_segments:
            render_commands["apply_blur"] = True
            render_commands["blur_start"] = min(seg["start"] for seg in cut_segments) / 1000.0
            render_commands["blur_end"] = max(seg["end"] for seg in cut_segments) / 1000.0

        if advanced_render_service.apply_advanced_effects(final_output_path, effect_output_path, render_commands):
            final_output_path = effect_output_path

    logger.info(f"Process completed successfully! Output: {final_output_path}")
    return {
        "status": "success",
        "message": "Video processed successfully",
        "output_video_url": f"/download/{os.path.basename(final_output_path)}",
        "output_edl_url": f"/download/{os.path.basename(output_edl_path)}",
        "matched_segments": build_output_timeline_segments(cut_segments)
    }

@router.post("/process_video_by_requirements")
async def process_video_by_requirements(
    file: UploadFile = File(...),
    requirements: str = Form(...),
    enable_redub: str = Form("false")
):
    is_redub = enable_redub.lower() == "true"
    logger.info(f"Received request to process video by requirements: {file.filename}, redub: {is_redub} (raw: {enable_redub})")
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    if not requirements:
        raise HTTPException(status_code=400, detail="Requirements are required")

    video_path = os.path.join(settings.UPLOAD_FOLDER, file.filename)
    base_name = os.path.splitext(file.filename)[0]
    audio_path = os.path.join(settings.AUDIO_FOLDER, f"{base_name}.wav")
    output_video_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}_cut.mp4")
    output_edl_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}.edl")

    logger.info("Step 1/6: Saving uploaded video file...")
    with open(video_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    logger.info("Step 2/6: Extracting audio from video...")
    if not asr_service.extract_audio_from_video(video_path, audio_path):
        logger.error("Audio extraction failed")
        raise HTTPException(status_code=500, detail="Audio extraction failed")

    logger.info("Step 3/6: Running FunASR speech recognition...")
    subtitles = asr_service.process_audio(audio_path)
    if not subtitles:
        logger.error("ASR recognition failed or returned empty")
        raise HTTPException(status_code=500, detail="ASR recognition failed or returned empty")
    logger.info(f"ASR completed. Generated {len(subtitles)} subtitle segments.")

    logger.info("Step 4/6: Generating script, segments and edit suggestions...")
    if is_redub:
        logger.info("Step 4/7 (Redub Round 1): Generating narration outline only...")
        outline = llm_service.generate_redub_outline(requirements, subtitles)
        script = outline.get("script", "")
        suggestions = outline.get("suggestions", [])
        effects = outline.get("effects", {"highlight": True, "blur": False})
        narration_segments = outline.get("narration_segments", [])
        if not narration_segments and script:
            narration_segments = [{"text": script, "focus": ""}]
        if not narration_segments:
            logger.error("No narration segments generated in redub round 1")
            raise HTTPException(status_code=500, detail="No narration segments generated")

        logger.info("Step 5/7 (Redub Local TTS): Synthesizing narration locally to measure exact durations...")
        measured_segments = measure_redub_narration(base_name, narration_segments)
        if not measured_segments:
            logger.error("Local TTS duration measurement failed")
            raise HTTPException(status_code=500, detail="Local TTS duration measurement failed")

        logger.info("Step 6/7 (Redub Round 2): Selecting final source clips using real TTS durations...")
        cut_segments = llm_service.generate_timed_redub_segments(requirements, subtitles, measured_segments)
        if not cut_segments:
            logger.error("No valid redub segments identified in round 2")
            raise HTTPException(status_code=500, detail="No valid redub segments identified")
        cut_segments = bind_measured_tts_to_segments(cut_segments, measured_segments)
        cut_segments = ensure_redub_segments_cover_tts(cut_segments, subtitles)
        script = build_dubbing_script(cut_segments) or script
    else:
        plan = llm_service.generate_requirements_plan(requirements, subtitles)
        script = plan.get("script", "")
        suggestions = plan.get("suggestions", [])
        effects = plan.get("effects", {"highlight": True, "blur": False})
        cut_segments = plan.get("segments", [])
        if not cut_segments and script:
            logger.info("Step 5/6: Segments not provided directly by LLM, falling back to aligning script with subtitles...")
            cut_segments = llm_service.align_script_with_subtitles(script, subtitles)
        if not cut_segments:
            logger.error("No valid segments identified for cutting")
            raise HTTPException(status_code=500, detail="No valid segments identified for cutting")

    logger.info("Segment selection completed. Identified %s segments to keep.", len(cut_segments))

    logger.info("Step 6/6: Exporting EDL project file...")
    export_service.export_to_edl(cut_segments, file.filename, output_edl_path)

    if is_redub:
        logger.info("Step 7/7 (Redub Mode): Cutting video, replacing audio per segment and preparing subtitles...")
        success, redub_subtitles = video_service.cut_and_concat_video_with_redub(video_path, output_video_path, cut_segments, tts_service)
        if not success:
            logger.error("Redub video editing failed")
            raise HTTPException(status_code=500, detail="Redub video editing failed")

        # 为时间线保留一份原视频音频版 cut，避免后续把配音烙死在源视频里。
        timeline_source_video_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}_timeline_source.mp4")
        if not video_service.cut_and_concat_video(video_path, timeline_source_video_path, cut_segments):
            logger.error("Timeline source video generation failed")
            raise HTTPException(status_code=500, detail="Timeline source video generation failed")
            
        # 针对配音模式，我们不再走之前的单文件全轨替换，因为音画不对齐。
        # 上面的方法已经做好了画面拼接和分段配音，现在我们只需要把 redub_subtitles 压制上去。
        final_output_path = output_video_path
        
        ass_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}_redub.ass")
        redub_video_with_sub = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}_redub.mp4")
        
        # 优化长字幕显示：字体稍微调小一点
        advanced_render_service.generate_ass_subtitle(
            redub_subtitles,
            ass_path,
            style_config={"font_size": 32}
        )
        
        render_commands = {"ass_file_path": ass_path}
        if advanced_render_service.apply_advanced_effects(final_output_path, redub_video_with_sub, render_commands):
            final_output_path = redub_video_with_sub

        voiceover_audio_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}_voiceover.mp3")
        if not video_service.extract_audio_track(output_video_path, voiceover_audio_path):
            voiceover_audio_path = ""

    else:
        logger.info("Step 6/6: Cutting and merging video clips (Original Audio)...")
        if not video_service.cut_and_concat_video(video_path, output_video_path, cut_segments):
            logger.error("Video editing failed")
            raise HTTPException(status_code=500, detail="Video editing failed")

        final_output_path = output_video_path
        timeline_source_video_path = output_video_path
        
        enable_effects = bool(effects.get("highlight", True)) or bool(effects.get("blur", False))
        apply_blur = bool(effects.get("blur", False))
        
        if enable_effects:
            ass_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}.ass")
            effect_output_path = os.path.join(settings.OUTPUT_FOLDER, f"{base_name}_fx.mp4")

            def overlaps(a_start, a_end, b_start, b_end):
                return not (a_end <= b_start or b_end <= a_start)

            highlighted_subtitles = []
            for s in subtitles:
                is_highlight = False
                for seg in cut_segments:
                    if overlaps(s["start"], s["end"], seg["start"], seg["end"]):
                        is_highlight = True
                        break
                item = dict(s)
                if is_highlight and effects.get("highlight", True):
                    item["is_highlight"] = True
                highlighted_subtitles.append(item)

            advanced_render_service.generate_ass_subtitle(
                highlighted_subtitles,
                ass_path,
                style_config={"font_size": 36}
            )

            render_commands = {"ass_file_path": ass_path}
            if apply_blur and cut_segments:
                render_commands["apply_blur"] = True
                render_commands["blur_start"] = min(seg["start"] for seg in cut_segments) / 1000.0
                render_commands["blur_end"] = max(seg["end"] for seg in cut_segments) / 1000.0

            if advanced_render_service.apply_advanced_effects(final_output_path, effect_output_path, render_commands):
                final_output_path = effect_output_path

    return {
        "status": "success",
        "message": "Video processed successfully",
        "output_video_url": f"/download/{os.path.basename(final_output_path)}",
        "output_edl_url": f"/download/{os.path.basename(output_edl_path)}",
        "timeline_source_video_url": f"/download/{os.path.basename(timeline_source_video_path)}",
        "voiceover_audio_url": f"/download/{os.path.basename(voiceover_audio_path)}" if voiceover_audio_path else "",
        "matched_segments": build_output_timeline_segments(cut_segments),
        "script": script,
        "suggestions": suggestions,
        "effects": effects,
        "redub_enabled": is_redub
    }


@router.post("/process_video_to_project")
async def process_video_to_project(
    file: UploadFile = File(...),
    requirements: str = Form(...),
    enable_redub: str = Form("false"),
    project_id: Optional[int] = Form(None),
    project_name: str = Form("AI自动剪辑项目"),
    create_export_job: bool = Form(True),
):
    is_redub = str(enable_redub).lower() == "true"
    ai_result = await process_video_by_requirements(
        file=file,
        requirements=requirements,
        enable_redub="true" if is_redub else "false",
    )
    try:
        return editor_ai_orchestrator.finalize_ai_result_to_project(
            ai_result=ai_result,
            is_redub=is_redub,
            project_id=project_id,
            project_name=project_name,
            create_export_job=bool(create_export_job),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
