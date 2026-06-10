import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.schemas.studio import AssetCreate, ProjectCreate
from app.services.editor_project_service import editor_project_service

from .common import ensure_project, probe_duration_ms, resolve_source_path_or_raise

router = APIRouter()


@router.get("/blueprint")
async def get_product_blueprint():
    return editor_project_service.get_blueprint()


@router.get("/overview")
async def get_studio_overview():
    return editor_project_service.get_overview()


@router.get("/effects/library")
async def get_effect_library():
    return {"items": editor_project_service.list_effect_presets()}


@router.get("/effects/catalog")
async def get_effect_catalog():
    return editor_project_service.get_effect_catalog()


@router.get("/projects")
async def list_projects():
    return {"items": editor_project_service.list_projects()}


@router.post("/projects")
async def create_project(payload: ProjectCreate):
    return editor_project_service.create_project(payload.model_dump())


@router.get("/projects/{project_id}")
async def get_project_detail(project_id: int):
    return ensure_project(project_id)


@router.post("/projects/{project_id}/assets")
async def create_project_asset(project_id: int, payload: AssetCreate):
    ensure_project(project_id)
    return editor_project_service.create_asset(project_id, payload.model_dump())


@router.post("/projects/{project_id}/assets/register")
async def register_project_asset(project_id: int, payload: AssetCreate):
    ensure_project(project_id)
    resolved = resolve_source_path_or_raise(payload.file_path or "")
    duration_ms = payload.duration_ms or 0
    if duration_ms <= 0:
        duration_ms = probe_duration_ms(resolved)
    asset = editor_project_service.register_existing_asset(
        project_id,
        {
            "name": payload.name,
            "file_type": payload.file_type,
            "file_path": payload.file_path,
            "duration_ms": duration_ms,
            "transcript_status": payload.transcript_status or "ready",
        },
    )
    if not asset:
        raise HTTPException(status_code=400, detail="Register asset failed")
    return asset


@router.post("/projects/{project_id}/assets/upload")
async def upload_project_asset(
    project_id: int,
    file: UploadFile = File(...),
    name: str = Form(""),
    transcript_status: str = Form("pending"),
):
    ensure_project(project_id)
    original_name = (name or file.filename or "").strip()
    if not original_name:
        raise HTTPException(status_code=400, detail="Missing asset name")
    ext = os.path.splitext(file.filename or "")[1]
    safe_filename = f"{os.urandom(8).hex()}{ext}"
    os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
    stored_path = os.path.join(settings.UPLOAD_FOLDER, safe_filename)
    try:
        content = await file.read()
        with open(stored_path, "wb") as handle:
            handle.write(content)
    finally:
        await file.close()
    content_type = (file.content_type or "").strip().lower()
    ext_type = os.path.splitext(original_name)[1].lstrip(".").lower()
    file_type = (content_type.split("/")[-1] if "/" in content_type else content_type) or ext_type or "media"
    if file_type in {"octet-stream", "application"} and ext_type:
        file_type = ext_type
    duration_ms = probe_duration_ms(stored_path)
    return editor_project_service.create_asset(
        project_id,
        {
            "name": original_name,
            "file_type": file_type,
            "file_path": stored_path,
            "duration_ms": duration_ms,
            "transcript_status": transcript_status or "pending",
        },
    )


@router.post("/projects/{project_id}/assets/{asset_id}/extract_audio")
async def extract_audio_from_project_asset(project_id: int, asset_id: int):
    ensure_project(project_id)
    audio_asset = editor_project_service.extract_audio_from_asset(project_id, asset_id)
    if not audio_asset:
        raise HTTPException(status_code=400, detail="Extract audio failed")
    return audio_asset


@router.delete("/projects/{project_id}/assets/{asset_id}")
async def delete_project_asset(project_id: int, asset_id: int):
    ensure_project(project_id)
    deleted = editor_project_service.delete_asset(project_id, asset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"status": "success"}


@router.post("/projects/{project_id}/assets/cleanup")
async def cleanup_project_assets(project_id: int):
    ensure_project(project_id)
    return editor_project_service.cleanup_missing_assets(project_id)


@router.post("/projects/{project_id}/reset")
async def reset_project_data(project_id: int, clear_assets: bool = True):
    ensure_project(project_id)
    result = editor_project_service.reset_project_data(project_id, clear_assets=clear_assets)
    if not result:
        raise HTTPException(status_code=400, detail="Reset project failed")
    return result
