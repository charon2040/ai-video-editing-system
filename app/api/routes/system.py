from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.api.auth_dependencies import current_user_id, get_current_user
from app.core.config import settings
from app.domain.schemas import ProjectKnowledgeUpdate, ProjectUpdate
from app.services.project_knowledge_service import project_knowledge_service
from app.services.project_service import project_service
from app.services.runtime_service import runtime_service
from app.workflows import workflow_registry


router = APIRouter(prefix=settings.api_prefix)


@router.get("/runtime")
async def get_runtime_status(user=Depends(get_current_user)):
    return runtime_service.get_runtime_status(user_id=current_user_id(user))


@router.get("/workflow-templates")
async def list_workflow_templates(user=Depends(get_current_user)):
    return {"items": workflow_registry.list_templates()}


@router.get("/projects")
async def list_projects(user=Depends(get_current_user)):
    return {"items": project_service.list_projects(user_id=current_user_id(user))}


@router.get("/projects/{project_id}")
async def get_project(project_id: str, user=Depends(get_current_user)):
    try:
        return project_service.get_project(project_id, user_id=current_user_id(user))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/projects")
async def create_project(payload: ProjectUpdate, user=Depends(get_current_user)):
    return project_service.create_project(
        title=payload.title or "新项目",
        description=payload.description or "",
        default_knowledge_base_id=payload.default_knowledge_base_id or "",
        default_pipeline_mode=payload.default_pipeline_mode or "narration_clip",
        default_knowledge_policy=payload.default_knowledge_policy or "none",
        default_duration_seconds=payload.default_duration_seconds or 0,
        default_style=payload.default_style or "summary",
        default_enable_dubbing=bool(payload.default_enable_dubbing),
        default_voice_mode=payload.default_voice_mode or "standard",
        default_voice_profile_id=payload.default_voice_profile_id or "",
        default_tts_speed=payload.default_tts_speed or 1.0,
        default_keep_original_audio=payload.default_keep_original_audio is not False,
        user_id=current_user_id(user),
    )


@router.put("/projects/{project_id}")
async def update_project(project_id: str, payload: ProjectUpdate, user=Depends(get_current_user)):
    try:
        return project_service.update_project(
            project_id=project_id,
            title=payload.title,
            description=payload.description,
            default_knowledge_base_id=payload.default_knowledge_base_id,
            default_pipeline_mode=payload.default_pipeline_mode,
            default_knowledge_policy=payload.default_knowledge_policy,
            default_duration_seconds=payload.default_duration_seconds,
            default_style=payload.default_style,
            default_enable_dubbing=payload.default_enable_dubbing,
            default_voice_mode=payload.default_voice_mode,
            default_voice_profile_id=payload.default_voice_profile_id,
            default_tts_speed=payload.default_tts_speed,
            default_keep_original_audio=payload.default_keep_original_audio,
            user_id=current_user_id(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user=Depends(get_current_user)):
    try:
        return project_service.delete_project(
            project_id,
            user_id=current_user_id(user),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        status_code = 409 if "Default project" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/project-knowledge")
async def list_project_knowledge(project_id: str = Query(""), user=Depends(get_current_user)):
    try:
        return {
            "items": project_knowledge_service.list_project_knowledge(
                project_id=project_id,
                user_id=current_user_id(user),
            )
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/project-knowledge/{knowledge_base_id}")
async def get_project_knowledge(knowledge_base_id: str, user=Depends(get_current_user)):
    return project_knowledge_service.get_project_knowledge(
        knowledge_base_id,
        user_id=current_user_id(user),
    )


@router.post("/project-knowledge")
async def create_project_knowledge(payload: ProjectKnowledgeUpdate, user=Depends(get_current_user)):
    try:
        return project_knowledge_service.create_project_knowledge(
            title=payload.title,
            content=payload.content,
            project_id=payload.project_id,
            user_id=current_user_id(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/project-knowledge/import")
async def import_project_knowledge(
    project_id: str = Form("default"),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    try:
        content = await file.read()
    finally:
        await file.close()

    try:
        return project_knowledge_service.import_project_knowledge_file(
            filename=file.filename or "",
            raw_content=content,
            project_id=project_id,
            user_id=current_user_id(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/project-knowledge")
async def update_project_knowledge(payload: ProjectKnowledgeUpdate, user=Depends(get_current_user)):
    user_id = current_user_id(user)
    try:
        project = project_service.get_project(payload.project_id, user_id=user_id)
        return project_knowledge_service.update_project_knowledge(
            knowledge_base_id=str(project.get("default_knowledge_base_id", "") or "default"),
            project_id=str(project.get("id", "") or "default"),
            title=payload.title,
            content=payload.content,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/project-knowledge/{knowledge_base_id}")
async def update_project_knowledge_by_id(
    knowledge_base_id: str,
    payload: ProjectKnowledgeUpdate,
    user=Depends(get_current_user),
):
    try:
        return project_knowledge_service.update_project_knowledge(
            knowledge_base_id=knowledge_base_id,
            project_id=payload.project_id,
            title=payload.title,
            content=payload.content,
            user_id=current_user_id(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/project-knowledge/{knowledge_base_id}")
async def delete_project_knowledge(
    knowledge_base_id: str,
    project_id: str = Query(""),
    user=Depends(get_current_user),
):
    try:
        return project_knowledge_service.delete_project_knowledge(
            knowledge_base_id=knowledge_base_id,
            project_id=project_id,
            user_id=current_user_id(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
