from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.core.config import settings
from app.services.task_store_service import task_store_service


class ProtectedFileService:
    _ROOTS = {
        "uploads": settings.upload_dir,
        "audio": settings.audio_dir,
        "outputs": settings.output_dir,
    }

    def resolve_file(self, root: str, file_path: str) -> Path:
        normalized_root = str(root or "").strip().lower()
        base_dir = self._ROOTS.get(normalized_root)
        if base_dir is None:
            raise ValueError("Unsupported file root")

        normalized_path = str(file_path or "").replace("\\", "/").strip("/")
        if not normalized_path or normalized_path.startswith("../") or "/../" in normalized_path:
            raise ValueError("Invalid file path")

        resolved_base = base_dir.resolve()
        resolved_path = (base_dir / normalized_path).resolve()
        try:
            resolved_path.relative_to(resolved_base)
        except ValueError as exc:
            raise ValueError("Invalid file path") from exc
        return resolved_path

    def user_can_access(self, *, root: str, file_path: str, user_id: str) -> bool:
        normalized_user_id = str(user_id or "").strip()
        if not normalized_user_id:
            return False

        normalized_path = str(file_path or "").replace("\\", "/").strip("/")
        if not normalized_path:
            return False
        requested_url = f"/{str(root or '').strip('/')}/{normalized_path}"

        for task in task_store_service.list_tasks(user_id=normalized_user_id):
            if self._artifact_url_matches(task, requested_url):
                return True
            if self._source_upload_matches(task, root=root, normalized_path=normalized_path):
                return True
            if self._asr_audio_matches(task, root=root, normalized_path=normalized_path):
                return True
        return False

    def _artifact_url_matches(self, task: Dict[str, Any], requested_url: str) -> bool:
        artifacts = task.get("artifacts", {}) if isinstance(task, dict) else {}
        if not isinstance(artifacts, dict):
            return False
        normalized_requested = str(requested_url or "").split("?", 1)[0]
        for value in artifacts.values():
            candidate = str(value or "").split("?", 1)[0]
            if candidate == normalized_requested:
                return True
        return False

    def _source_upload_matches(self, task: Dict[str, Any], *, root: str, normalized_path: str) -> bool:
        if str(root or "").strip().lower() != "uploads":
            return False
        source_path = Path(str(task.get("source_path", "") or ""))
        return source_path.name == Path(normalized_path).name

    def _asr_audio_matches(self, task: Dict[str, Any], *, root: str, normalized_path: str) -> bool:
        if str(root or "").strip().lower() != "audio":
            return False
        source_hash = str(task.get("source_hash", "") or "").strip()
        if not source_hash:
            return False
        return Path(normalized_path).name == f"cache_{source_hash[:16]}.wav"


protected_file_service = ProtectedFileService()
