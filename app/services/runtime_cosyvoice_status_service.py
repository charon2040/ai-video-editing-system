from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from app.core.config import settings
from app.services.cosyvoice_runtime_service import cosyvoice_runtime_service
from app.services.runtime_probe_service import runtime_probe_service


class RuntimeCosyVoiceStatusService:
    def provider_mode(self, provider: str) -> str:
        value = str(provider or "").strip().lower()
        if value == "mock":
            return "mock"
        if value in {"cosyvoice", "cosyvoice_service"}:
            return "persistent_local_service"
        if value in {"cosyvoice_local", "local_cosyvoice"}:
            return "subprocess_local_model"
        if value in {"cosyvoice_http"}:
            return "http_service"
        return value or "unknown"

    def build_status(self, *, registered_profiles: list[dict]) -> Dict[str, Any]:
        provider = str(settings.tts_provider or "cosyvoice").strip().lower()
        provider_mode = self.provider_mode(provider)
        python_path = Path(settings.cosyvoice_local_python)
        repo_dir = Path(settings.cosyvoice_repo_dir)
        model_dir = Path(settings.cosyvoice_model_dir)
        helper_path = settings.cosyvoice_helper_path
        service_path = settings.cosyvoice_service_path
        modules = ["torch", "torchaudio", "onnxruntime"]
        probe = runtime_probe_service.probe_external_python(python_path, modules)
        service_status: Dict[str, Any] = {}
        if provider_mode == "persistent_local_service":
            service_status = cosyvoice_runtime_service.get_service_status(timeout=2.0)

        ready = False
        if provider_mode == "mock":
            ready = True
        elif provider_mode == "http_service":
            ready = True
        elif provider_mode == "persistent_local_service":
            ready = (
                bool(probe.get("exists"))
                and bool(probe.get("modules", {}).get("torch"))
                and bool(probe.get("modules", {}).get("torchaudio"))
                and repo_dir.exists()
                and model_dir.exists()
                and service_path.exists()
                and bool(service_status.get("healthy"))
            )
        elif provider_mode == "subprocess_local_model":
            ready = (
                bool(probe.get("exists"))
                and bool(probe.get("modules", {}).get("torch"))
                and bool(probe.get("modules", {}).get("torchaudio"))
                and repo_dir.exists()
                and model_dir.exists()
                and helper_path.exists()
            )

        payload = service_status.get("payload", {}) or {}
        return {
            "provider": provider,
            "mode": provider_mode,
            "ready": ready,
            "python": probe.get("python", str(python_path)),
            "python_exists": bool(probe.get("exists")),
            "repo_dir": str(repo_dir),
            "repo_exists": repo_dir.exists(),
            "model_dir": str(model_dir),
            "model_exists": model_dir.exists(),
            "helper_path": str(helper_path),
            "helper_exists": helper_path.exists(),
            "service_path": str(service_path),
            "service_exists": service_path.exists(),
            "service_healthy": bool(service_status.get("healthy")) if service_status else False,
            "service_pid": service_status.get("pid") if service_status else None,
            "service_model_type": payload.get("model_type", ""),
            "native_speaker_count": int(payload.get("native_speaker_count", 0) or 0),
            "profile_speaker_count": int(payload.get("profile_speaker_count", 0) or 0),
            "registered_profile_count": len(registered_profiles),
            "modules": probe.get("modules", {}),
            "http_base_url": settings.cosyvoice_base_url if provider_mode in {"http_service", "persistent_local_service"} else "",
            "detail": payload,
        }


runtime_cosyvoice_status_service = RuntimeCosyVoiceStatusService()
