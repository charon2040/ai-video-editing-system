from __future__ import annotations

import sys
import time
from typing import Any, Dict

from app.core.config import BASE_DIR, settings
from app.services.asr_service import asr_service
from app.services.runtime_cosyvoice_status_service import runtime_cosyvoice_status_service
from app.services.runtime_probe_service import runtime_probe_service
from app.services.voice_profile_service import voice_profile_service


class RuntimeService:
    def __init__(self) -> None:
        self._cache_by_user: Dict[str, Dict[str, Any]] = {}
        self._cache_at_by_user: Dict[str, float] = {}

    def _build_status(self, *, user_id: str = "") -> Dict[str, Any]:
        profiles = voice_profile_service.list_profiles(active_only=True, user_id=user_id)
        standard_profiles = [
            item for item in profiles
            if str(item.get("source_type", "") or "").strip().lower() != "user"
        ]
        clone_profiles = [
            item for item in profiles
            if str(item.get("source_type", "") or "").strip().lower() == "user"
        ]
        cosyvoice_status = runtime_cosyvoice_status_service.build_status(
            registered_profiles=clone_profiles
        )

        return {
            "topology": {
                "separate_envs": True,
                "summary": "ASR 在主后端环境内运行；普通配音和克隆配音都走 CosyVoice 常驻服务。",
            },
            "backend": {
                "python": sys.executable,
                "project_dir": str(BASE_DIR),
            },
            "llm": {
                "configured": bool(settings.llm_api_key),
                "base_url": settings.llm_base_url,
                "model": settings.llm_model,
            },
            "asr": {
                "ready": runtime_probe_service.module_available("funasr"),
                "mode": "in_process",
                "python": sys.executable,
                "device": asr_service._detect_device(),
                "model": settings.funasr_model,
                "vad_model": settings.funasr_vad_model,
                "punc_model": settings.funasr_punc_model,
            },
            "tts": {
                "ready": bool(cosyvoice_status.get("ready")),
                "provider": settings.tts_provider,
                "mode": "cosyvoice_only",
                "default_mode": settings.tts_default_mode,
                "standard_provider": settings.tts_standard_provider,
                "clone_provider": settings.tts_clone_provider,
                "standard_profile_count": len(standard_profiles),
                "clone_profile_count": len(clone_profiles),
                "cosyvoice": cosyvoice_status,
                "standard": cosyvoice_status,
                "clone": cosyvoice_status,
            },
        }

    def get_runtime_status(self, force_refresh: bool = False, *, user_id: str = "") -> Dict[str, Any]:
        now = time.time()
        cache_key = str(user_id or "local").strip() or "local"
        cached = self._cache_by_user.get(cache_key)
        cached_at = float(self._cache_at_by_user.get(cache_key, 0.0) or 0.0)
        if not force_refresh and cached is not None and now - cached_at < 10:
            return cached

        payload = self._build_status(user_id=cache_key)
        self._cache_by_user[cache_key] = payload
        self._cache_at_by_user[cache_key] = now
        return payload


runtime_service = RuntimeService()
