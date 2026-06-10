import os
import subprocess

from fastapi import HTTPException

from app.services.editor_project_service import editor_project_service


def ensure_project(project_id: int):
    project = editor_project_service.get_project_detail(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def probe_duration_ms(file_path: str) -> int:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        duration_sec = float(result.stdout.strip())
        return max(0, int(duration_sec * 1000))
    except Exception:
        return 0


def resolve_source_path_or_raise(file_path: str) -> str:
    resolved = editor_project_service.resolve_storage_path(file_path or "")
    if not resolved or not os.path.exists(resolved):
        raise HTTPException(status_code=400, detail="Source file not found")
    return resolved
