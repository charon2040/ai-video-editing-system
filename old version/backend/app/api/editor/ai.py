from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.api.endpoints import video

router = APIRouter()


@router.post("/ai/generate")
async def generate_ai_project(
    file: UploadFile = File(...),
    requirements: str = Form(...),
    enable_redub: str = Form("false"),
    project_id: Optional[int] = Form(None),
    project_name: str = Form("AI自动剪辑项目"),
    create_export_job: bool = Form(True),
):
    return await video.process_video_to_project(
        file=file,
        requirements=requirements,
        enable_redub=enable_redub,
        project_id=project_id,
        project_name=project_name,
        create_export_job=create_export_job,
    )
