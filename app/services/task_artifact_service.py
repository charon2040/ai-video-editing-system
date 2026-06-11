from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import settings


class TaskArtifactService:
    def _safe_unlink(self, path: Path, *, base_dir: Path) -> bool:
        try:
            resolved_base = base_dir.resolve()
            resolved_path = path.resolve()
            resolved_path.relative_to(resolved_base)
        except Exception:
            return False

        if resolved_path.is_file():
            resolved_path.unlink(missing_ok=True)
            return True
        return False

    def _safe_rmtree(self, path: Path, *, base_dir: Path) -> bool:
        try:
            resolved_base = base_dir.resolve()
            resolved_path = path.resolve()
            resolved_path.relative_to(resolved_base)
        except Exception:
            return False

        if resolved_path.is_dir():
            shutil.rmtree(resolved_path, ignore_errors=True)
            return True
        return False

    def cleanup_task_runtime_files(self, task_id: str) -> Dict[str, Any]:
        deleted_files: List[str] = []
        deleted_dirs: List[str] = []
        for path in settings.output_dir.glob(f"{task_id}_*"):
            if self._safe_unlink(path, base_dir=settings.output_dir):
                deleted_files.append(str(path))

        for path in settings.voiceover_dir.glob(f"{task_id}_*"):
            if self._safe_unlink(path, base_dir=settings.voiceover_dir):
                deleted_files.append(str(path))

        voiceover_task_dir = settings.voiceover_dir / task_id
        if self._safe_rmtree(voiceover_task_dir, base_dir=settings.voiceover_dir):
            deleted_dirs.append(str(voiceover_task_dir))

        return {
            "deleted_runtime_files": deleted_files,
            "deleted_runtime_dirs": deleted_dirs,
        }

    def cleanup_source_file(self, task: Dict[str, Any]) -> Dict[str, Any]:
        source_path = Path(str(task.get("source_path", "") or ""))
        deleted = self._safe_unlink(source_path, base_dir=settings.upload_dir) if str(source_path) else False
        return {
            "deleted_source": deleted,
            "source_path": str(source_path) if deleted else "",
        }

    def cleanup_asr_cache_files(self, task: Dict[str, Any], cached: Dict[str, Any] | None = None) -> Dict[str, Any]:
        source_hash = str(task.get("source_hash", "") or "").strip()
        candidate_paths: List[Path] = []
        if cached:
            cached_audio_path = str(cached.get("audio_path", "") or "").strip()
            if cached_audio_path:
                candidate_paths.append(Path(cached_audio_path))
        if source_hash:
            candidate_paths.append(settings.audio_dir / f"cache_{source_hash[:16]}.wav")

        deleted_files: List[str] = []
        seen: set[str] = set()
        for path in candidate_paths:
            key = str(path)
            if not key or key in seen:
                continue
            seen.add(key)
            if self._safe_unlink(path, base_dir=settings.audio_dir):
                deleted_files.append(str(path))

        return {
            "deleted_asr_cache_files": deleted_files,
            "deleted_asr_cache_audio": bool(deleted_files),
        }


task_artifact_service = TaskArtifactService()
