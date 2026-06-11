from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List

from app.core.db import app_db
from app.services.voice_profile_manifest_service import voice_profile_manifest_service


class VoiceProfileService:
    def __init__(self) -> None:
        self._synced = False

    def _now_iso(self) -> str:
        return voice_profile_manifest_service.now_iso()

    def _build_user_profile_id(self, label: str) -> str:
        slug = voice_profile_manifest_service.slugify_profile_id(label)
        digest = hashlib.sha1(f"{label}|{self._now_iso()}".encode("utf-8")).hexdigest()[:8]
        return f"user_{slug}_{digest}"

    def _resolve_profile_path(self, raw_path: str) -> Path:
        return voice_profile_manifest_service.resolve_profile_path(raw_path)

    def resolve_prompt_wav_path(self, profile: Dict[str, Any]) -> Path:
        return voice_profile_manifest_service.resolve_prompt_wav_path(profile)

    def runtime_manifest_path(self) -> Path:
        return voice_profile_manifest_service.runtime_manifest_path()

    def export_runtime_manifest(self) -> Path:
        app_db.init_schema()
        return voice_profile_manifest_service.export_runtime_manifest(
            app_db.list_voice_profiles(active_only=True)
        )

    def sync_manifest_to_db(self) -> List[Dict[str, Any]]:
        now_iso = self._now_iso()
        seed_profiles = voice_profile_manifest_service.load_seed_profiles()
        existing_by_id = {
            item.get("id", ""): item
            for item in app_db.list_voice_profiles(active_only=False)
            if item.get("id")
        }

        seed_ids = {str(item.get("id", "") or "") for item in seed_profiles}
        for item in seed_profiles:
            existing = existing_by_id.get(str(item.get("id", "") or ""), {})
            record = {
                "id": item["id"],
                "label": item["label"],
                "description": item["description"],
                "prompt_text": item["prompt_text"],
                "prompt_wav_path": item["prompt_wav_path"],
                "language": item["language"],
                "source_type": "seed",
                "is_default": item["is_default"],
                "is_active": item["is_active"],
                "sort_order": item["sort_order"],
                "created_at": str(existing.get("created_at", "") or now_iso),
                "updated_at": now_iso,
            }
            app_db.upsert_voice_profile(record)

        for profile_id, existing in existing_by_id.items():
            if existing.get("source_type") != "seed":
                continue
            if profile_id in seed_ids:
                continue
            app_db.upsert_voice_profile(
                {
                    **existing,
                    "is_active": False,
                    "updated_at": now_iso,
                }
            )

        self._synced = True
        self.export_runtime_manifest()
        return [
            self._serialize_profile(item)
            for item in app_db.list_voice_profiles(active_only=False)
        ]

    def ensure_synced(self) -> None:
        app_db.init_schema()
        if not self._synced or not app_db.list_voice_profiles(active_only=False):
            self.sync_manifest_to_db()
            return
        if not self.runtime_manifest_path().exists():
            self.export_runtime_manifest()

    def _serialize_profile(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        if not profile:
            return {}
        resolved_wav_path = self.resolve_prompt_wav_path(profile)
        return {
            **profile,
            "prompt_wav_exists": resolved_wav_path.exists(),
            "prompt_wav_abs_path": str(resolved_wav_path),
        }

    def list_profiles(self, *, active_only: bool = True, user_id: str = "") -> List[Dict[str, Any]]:
        self.ensure_synced()
        return [
            self._serialize_profile(item)
            for item in app_db.list_voice_profiles(active_only=active_only, user_id=user_id)
        ]

    def get_profile(self, profile_id: str, *, user_id: str = "") -> Dict[str, Any]:
        self.ensure_synced()
        return self._serialize_profile(
            app_db.get_voice_profile(str(profile_id or "").strip(), user_id=user_id)
        )

    def find_profile_by_label(self, label: str, *, user_id: str = "") -> Dict[str, Any]:
        self.ensure_synced()
        return self._serialize_profile(
            app_db.find_voice_profile_by_label(str(label or "").strip(), user_id=user_id)
        )

    def get_default_profile(self, *, user_id: str = "") -> Dict[str, Any]:
        profiles = self.list_profiles(active_only=True, user_id=user_id)
        if not profiles:
            return {}
        for item in profiles:
            if item.get("is_default"):
                return item
        return profiles[0]

    def resolve_profile(
        self,
        profile_ref: str = "",
        *,
        label: str = "",
        allow_default: bool = True,
        user_id: str = "",
    ) -> Dict[str, Any]:
        normalized_ref = str(profile_ref or "").strip()
        normalized_label = str(label or "").strip()

        profile: Dict[str, Any] = {}
        if normalized_ref:
            profile = self.get_profile(normalized_ref, user_id=user_id)
            if not profile:
                profile = self.find_profile_by_label(normalized_ref, user_id=user_id)
        if not profile and normalized_label:
            profile = self.find_profile_by_label(normalized_label, user_id=user_id)
        if profile and profile.get("is_active") is False:
            profile = {}
        if not profile and allow_default:
            profile = self.get_default_profile(user_id=user_id)
        return profile

    def _next_sort_order(self, *, user_id: str = "") -> int:
        profiles = app_db.list_voice_profiles(active_only=False, user_id=user_id)
        if not profiles:
            return 100
        return max(int(item.get("sort_order", 0) or 0) for item in profiles) + 10

    def create_user_profile(
        self,
        *,
        label: str,
        description: str,
        language: str,
        prompt_text: str,
        prompt_wav_path: str,
        user_id: str = "local",
    ) -> Dict[str, Any]:
        self.ensure_synced()
        normalized_user_id = str(user_id or "local").strip() or "local"

        normalized_label = str(label or "").strip()
        normalized_prompt_text = str(prompt_text or "").strip()
        normalized_language = str(language or "").strip()
        normalized_description = str(description or "").strip()
        normalized_prompt_wav_path = str(prompt_wav_path or "").strip()

        if not normalized_label:
            raise ValueError("模板名称不能为空")
        if not normalized_prompt_text:
            raise ValueError("参考文案不能为空")
        if not normalized_prompt_wav_path:
            raise ValueError("参考音频不能为空")

        existing = self.find_profile_by_label(normalized_label, user_id=normalized_user_id)
        if existing and existing.get("is_active"):
            raise ValueError("已存在同名配音模板，请换一个名称")

        wav_path = self._resolve_profile_path(normalized_prompt_wav_path)
        if not wav_path.exists():
            raise ValueError("参考音频文件不存在")

        now_iso = self._now_iso()
        profile_id = self._build_user_profile_id(normalized_label)
        record = {
            "id": profile_id,
            "user_id": normalized_user_id,
            "label": normalized_label,
            "description": normalized_description,
            "prompt_text": normalized_prompt_text,
            "prompt_wav_path": normalized_prompt_wav_path,
            "language": normalized_language,
            "source_type": "user",
            "is_default": False,
            "is_active": True,
            "sort_order": self._next_sort_order(user_id=normalized_user_id),
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        app_db.upsert_voice_profile(record)
        self.export_runtime_manifest()
        return self.get_profile(profile_id, user_id=normalized_user_id)


voice_profile_service = VoiceProfileService()
