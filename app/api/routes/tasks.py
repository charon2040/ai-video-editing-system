from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.auth_dependencies import current_user_id, get_current_user
from app.api.task_form_normalizer import (
    build_create_options,
    build_replan_options,
    normalize_beats_json,
)
from app.core.config import settings
from app.services.task_service import task_service


router = APIRouter(prefix=settings.api_prefix)


@router.get("/tasks")
async def list_tasks(project_id: str = "", user=Depends(get_current_user)):
    user_id = current_user_id(user)
    return {"items": task_service.list_tasks(project_id=project_id, user_id=user_id)}


@router.delete("/tasks")
async def clear_finished_tasks(
    scope: str = "finished",
    project_id: str = "",
    delete_source: bool = False,
    user=Depends(get_current_user),
):
    if str(scope or "").strip() != "finished":
        raise HTTPException(status_code=400, detail="Unsupported delete scope")
    return task_service.delete_finished_tasks(
        project_id=project_id,
        user_id=current_user_id(user),
        delete_source=delete_source,
    )


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, user=Depends(get_current_user)):
    task = task_service.get_task(task_id, user_id=current_user_id(user))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/tasks/{task_id}/events")
async def list_task_events(task_id: str, user=Depends(get_current_user)):
    user_id = current_user_id(user)
    task = task_service.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"items": task_service.list_task_events(task_id, user_id=user_id)}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    delete_source: bool = False,
    user=Depends(get_current_user),
):
    user_id = current_user_id(user)
    task = task_service.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        return task_service.delete_task(task_id, user_id=user_id, delete_source=delete_source)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/plans")
async def list_task_plans(task_id: str, user=Depends(get_current_user)):
    user_id = current_user_id(user)
    task = task_service.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"items": task_service.list_clip_plans(task_id, user_id=user_id)}


@router.post("/tasks")
async def create_task(
    file: UploadFile = File(...),
    requirements: str = Form(""),
    target_script: str = Form(""),
    project_id: str = Form("default"),
    pipeline_mode: str = Form(""),
    project_context: str = Form(""),
    knowledge_policy: str = Form("none"),
    knowledge_base_id: str = Form(""),
    duration_seconds: int = Form(0),
    style: str = Form("summary"),
    enable_dubbing: str = Form("false"),
    voice_source: str = Form("tts"),
    voice_mode: str = Form("standard"),
    voice_profile_id: str = Form(""),
    tts_voice: str = Form(""),
    tts_speed: float = Form(1.0),
    keep_original_audio: str = Form("true"),
    uploaded_voiceover: UploadFile | None = File(None),
    user=Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing upload file")

    options = build_create_options(
        requirements=requirements,
        target_script=target_script,
        project_id=project_id,
        pipeline_mode=pipeline_mode,
        project_context=project_context,
        knowledge_policy=knowledge_policy,
        knowledge_base_id=knowledge_base_id,
        duration_seconds=duration_seconds,
        style=style,
        enable_dubbing=enable_dubbing,
        voice_source=voice_source,
        voice_mode=voice_mode,
        voice_profile_id=voice_profile_id,
        tts_voice=tts_voice,
        tts_speed=tts_speed,
        keep_original_audio=keep_original_audio,
    )

    try:
        content = await file.read()
    finally:
        await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="上传视频文件为空。")

    uploaded_voiceover_filename = ""
    uploaded_voiceover_content: bytes | None = None
    if options.voice_source == "uploaded_voiceover":
        if not uploaded_voiceover or not uploaded_voiceover.filename:
            raise HTTPException(status_code=400, detail="上传完整配音模式需要提供配音音频文件。")
        try:
            uploaded_voiceover_filename = uploaded_voiceover.filename
            uploaded_voiceover_content = await uploaded_voiceover.read()
        finally:
            await uploaded_voiceover.close()
        if not uploaded_voiceover_content:
            raise HTTPException(status_code=400, detail="上传配音音频为空。")
    elif uploaded_voiceover is not None:
        await uploaded_voiceover.close()

    suffix = "".join(Path(file.filename).suffixes) or ".mp4"
    safe_name = f"{sha256((file.filename + options.request_text).encode('utf-8')).hexdigest()[:12]}{suffix}"
    source_path = settings.upload_dir / safe_name
    source_hash = sha256(content).hexdigest()
    source_path.write_bytes(content)

    try:
        return task_service.create_task(
            source_path=source_path,
            source_hash=source_hash,
            source_size=len(content),
            original_filename=file.filename,
            request_text=options.request_text,
            request_mode=options.request_mode,
            project_id=options.project_id,
            pipeline_mode=options.pipeline_mode,
            project_context=options.project_context,
            knowledge_policy=options.knowledge_policy,
            knowledge_base_id=options.knowledge_base_id,
            duration_seconds=options.duration_seconds,
            style=options.style,
            enable_dubbing=options.enable_dubbing,
            voice_source=options.voice_source,
            voice_mode=options.voice_mode,
            voice_profile_id=options.voice_profile_id,
            tts_voice=options.tts_voice,
            tts_speed=options.tts_speed,
            keep_original_audio=options.keep_original_audio,
            uploaded_voiceover_filename=uploaded_voiceover_filename,
            uploaded_voiceover_content=uploaded_voiceover_content,
            user_id=current_user_id(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/replan")
async def replan_task(
    task_id: str,
    requirements: str = Form(""),
    target_script: str = Form(""),
    project_id: str = Form(""),
    pipeline_mode: str = Form(""),
    project_context: str = Form(""),
    knowledge_policy: str = Form(""),
    knowledge_base_id: str = Form(""),
    duration_seconds: int = Form(0),
    style: str = Form("summary"),
    enable_dubbing: str = Form(""),
    voice_mode: str = Form(""),
    voice_profile_id: str = Form(""),
    tts_voice: str = Form(""),
    tts_speed: str = Form(""),
    keep_original_audio: str = Form(""),
    user=Depends(get_current_user),
):
    user_id = current_user_id(user)
    base_task = task_service.get_task(task_id, user_id=user_id)
    if not base_task:
        raise HTTPException(status_code=404, detail="Base task not found")

    try:
        options = build_replan_options(
            base_task=base_task,
            requirements=requirements,
            target_script=target_script,
            project_id=project_id,
            pipeline_mode=pipeline_mode,
            project_context=project_context,
            knowledge_policy=knowledge_policy,
            knowledge_base_id=knowledge_base_id,
            duration_seconds=duration_seconds,
            style=style,
            enable_dubbing=enable_dubbing,
            voice_source="tts",
            voice_mode=voice_mode,
            voice_profile_id=voice_profile_id,
            tts_voice=tts_voice,
            tts_speed=tts_speed,
            keep_original_audio=keep_original_audio,
        )
        return task_service.create_task_from_existing_source(
            base_task_id=task_id,
            request_text=options.request_text,
            request_mode=options.request_mode,
            project_id=options.project_id,
            pipeline_mode=options.pipeline_mode,
            project_context=options.project_context,
            knowledge_policy=options.knowledge_policy,
            knowledge_base_id=options.knowledge_base_id,
            duration_seconds=options.duration_seconds,
            style=options.style,
            enable_dubbing=options.enable_dubbing,
            voice_source=options.voice_source,
            voice_mode=options.voice_mode,
            voice_profile_id=options.voice_profile_id,
            tts_voice=options.tts_voice,
            tts_speed=options.tts_speed,
            keep_original_audio=options.keep_original_audio,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/draft")
async def update_task_draft(
    task_id: str,
    draft_script: str = Form(""),
    beats_json: str = Form("[]"),
    user=Depends(get_current_user),
):
    user_id = current_user_id(user)
    task = task_service.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        return task_service.update_draft(
            task_id,
            draft_script=str(draft_script or "").strip(),
            draft_beats=normalize_beats_json(beats_json),
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/approve-draft")
async def approve_task_draft(
    task_id: str,
    draft_script: str = Form(""),
    beats_json: str = Form("[]"),
    user=Depends(get_current_user),
):
    user_id = current_user_id(user)
    task = task_service.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        return task_service.approve_draft(
            task_id,
            draft_script=str(draft_script or "").strip(),
            draft_beats=normalize_beats_json(beats_json),
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/retry-alignment")
async def retry_task_alignment(task_id: str, user=Depends(get_current_user)):
    user_id = current_user_id(user)
    task = task_service.get_task(task_id, user_id=user_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    try:
        return task_service.retry_alignment(task_id, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
