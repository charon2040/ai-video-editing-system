from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.auth_dependencies import current_user_id, get_current_user
from app.services.protected_file_service import protected_file_service


router = APIRouter()


def _serve_protected_file(root: str, file_path: str, user: dict) -> FileResponse:
    try:
        resolved_path = protected_file_service.resolve_file(root, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="File not found") from exc

    user_id = current_user_id(user)
    if not protected_file_service.user_can_access(
        root=root,
        file_path=file_path,
        user_id=user_id,
    ):
        raise HTTPException(status_code=404, detail="File not found")
    if not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(resolved_path, filename=resolved_path.name)


@router.get("/uploads/{file_path:path}")
async def get_upload_file(file_path: str, user=Depends(get_current_user)):
    return _serve_protected_file("uploads", file_path, user)


@router.get("/audio/{file_path:path}")
async def get_audio_file(file_path: str, user=Depends(get_current_user)):
    return _serve_protected_file("audio", file_path, user)


@router.get("/outputs/{file_path:path}")
async def get_output_file(file_path: str, user=Depends(get_current_user)):
    return _serve_protected_file("outputs", file_path, user)
