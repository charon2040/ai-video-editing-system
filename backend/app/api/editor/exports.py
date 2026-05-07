from fastapi import APIRouter, HTTPException

from app.schemas.studio import ExportJobCreate
from app.services.editor_export_service import editor_export_service

from .common import ensure_project

router = APIRouter()


@router.get("/projects/{project_id}/exports")
async def list_project_exports(project_id: int):
    ensure_project(project_id)
    return {"items": editor_export_service.list_export_jobs(project_id)}


@router.post("/projects/{project_id}/exports")
async def create_export_job(project_id: int, payload: ExportJobCreate):
    ensure_project(project_id)
    return editor_export_service.create_export_job(project_id, payload.model_dump())


@router.get("/projects/{project_id}/exports/{job_id}")
async def get_project_export_job(project_id: int, job_id: int):
    ensure_project(project_id)
    job = editor_export_service.get_export_job(project_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")
    return job
