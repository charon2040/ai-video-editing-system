import os
import json
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.asr_service import asr_service
from app.services.llm_service import llm_service
from app.services.video_service import video_service
from app.services.export_service import export_service
from app.services.advanced_render_service import advanced_render_service
from app.services.tts_service import tts_service
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

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

    if is_redub:
        normalized_segments = []
        for seg in cut_segments:
            item = dict(seg)
            dubbing = str(item.get("dubbing", "")).strip()
            if not dubbing:
                dubbing = str(item.get("content", "")).strip()
            item["dubbing"] = dubbing
            normalized_segments.append(item)
        cut_segments = normalized_segments
        if script:
            cut_segments = llm_service.project_script_to_segments(script, cut_segments)
        actual_dubbing_script = build_dubbing_script(cut_segments)
        if actual_dubbing_script:
            script = actual_dubbing_script
        
    logger.info(f"LLM alignment/segment selection completed. Identified {len(cut_segments)} segments to keep.")

    logger.info("Step 6/6: Exporting EDL project file...")
    export_service.export_to_edl(cut_segments, file.filename, output_edl_path)

    if is_redub:
        logger.info("Step 6/6 (Redub Mode): Cutting video, replacing audio per segment and preparing subtitles...")
        success, redub_subtitles = video_service.cut_and_concat_video_with_redub(video_path, output_video_path, cut_segments, tts_service)
        if not success:
            logger.error("Redub video editing failed")
            raise HTTPException(status_code=500, detail="Redub video editing failed")
            
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

    else:
        logger.info("Step 6/6: Cutting and merging video clips (Original Audio)...")
        if not video_service.cut_and_concat_video(video_path, output_video_path, cut_segments):
            logger.error("Video editing failed")
            raise HTTPException(status_code=500, detail="Video editing failed")

        final_output_path = output_video_path
        
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
        "matched_segments": build_output_timeline_segments(cut_segments),
        "script": script,
        "suggestions": suggestions,
        "effects": effects
    }
