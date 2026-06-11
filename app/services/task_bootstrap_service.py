from __future__ import annotations

import logging

from app.services.task_event_service import now_iso
from app.services.task_store_service import task_store_service
from app.services.voice_profile_service import voice_profile_service


logger = logging.getLogger(__name__)


class TaskBootstrapService:
    def initialize(self) -> None:
        storage_result = task_store_service.initialize_storage()
        migrated = int(storage_result.get("migrated_legacy_tasks", 0) or 0)
        if migrated:
            logger.info("Migrated %s legacy tasks into SQLite.", migrated)
        merged = storage_result.get("merged_external_database", {}) or {}
        if any(merged.values()):
            logger.info(
                "Merged misplaced database rows into SQLite: tasks=%s asr_cache=%s clip_plans=%s",
                merged["tasks"],
                merged["asr_cache"],
                merged["clip_plans"],
            )
        profiles = voice_profile_service.sync_manifest_to_db()
        if profiles:
            logger.info("Voice profiles ready: count=%s", len(profiles))

    def recover_interrupted_tasks(self) -> int:
        return task_store_service.recover_interrupted_tasks(now_iso())


task_bootstrap_service = TaskBootstrapService()
