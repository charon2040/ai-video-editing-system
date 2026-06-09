from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List

from app.core.db import app_db
from app.services.project_service import DEFAULT_PROJECT_ID, project_service


PROJECT_CONTEXT_LIMIT = 12000
PROJECT_KNOWLEDGE_LIMIT = 20000


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ProjectKnowledgeService:
    def _knowledge_belongs_to_project(self, knowledge_base_id: str, project_id: str, user_id: str) -> bool:
        knowledge = app_db.get_project_knowledge(knowledge_base_id, user_id=user_id)
        exists = bool(str(knowledge.get("created_at", "") or knowledge.get("updated_at", "") or "").strip())
        return exists and str(knowledge.get("project_id", "") or DEFAULT_PROJECT_ID) == project_id

    def _repair_project_default_knowledge(self, project: Dict, items: List[Dict], user_id: str) -> str:
        project_id = str(project.get("id", "") or DEFAULT_PROJECT_ID).strip() or DEFAULT_PROJECT_ID
        default_id = str(project.get("default_knowledge_base_id", "") or "").strip()
        if default_id and self._knowledge_belongs_to_project(default_id, project_id, user_id):
            return default_id

        replacement_id = str(items[0].get("id", "") or "").strip() if items else ""
        if not replacement_id:
            replacement_id = "default" if project_id == DEFAULT_PROJECT_ID else f"{project_id}_default_kb"

        project_service.update_project(
            project_id=project_id,
            default_knowledge_base_id=replacement_id,
            user_id=user_id,
            allow_missing_default_knowledge=not bool(items),
        )
        return replacement_id

    def list_project_knowledge(self, project_id: str = "", *, user_id: str = "local") -> List[Dict]:
        normalized_user_id = str(user_id or "local").strip() or "local"
        normalized_project_id = str(project_id or "").strip()
        project: Dict = {}
        if normalized_project_id:
            project = project_service.get_project(normalized_project_id, user_id=normalized_user_id)
        items = app_db.list_project_knowledge(project_id=normalized_project_id, user_id=normalized_user_id)
        if normalized_project_id:
            default_id = self._repair_project_default_knowledge(project, items, normalized_user_id)
        else:
            default_id = ""
        if normalized_project_id and not items:
            items = [
                app_db.upsert_project_knowledge(
                    title=f"{str(project.get('title', '') or '项目')}知识库",
                    content="",
                    now_iso=_now_iso(),
                    knowledge_id=default_id,
                    project_id=normalized_project_id,
                    user_id=normalized_user_id,
                )
            ]
        return items

    def get_project_knowledge(self, knowledge_base_id: str = "default", *, user_id: str = "local") -> Dict:
        return app_db.get_project_knowledge(knowledge_base_id, user_id=user_id)

    def create_project_knowledge(
        self,
        *,
        title: str = "",
        content: str = "",
        project_id: str = DEFAULT_PROJECT_ID,
        user_id: str = "local",
    ) -> Dict:
        return self.update_project_knowledge(
            knowledge_base_id=f"kb_{uuid.uuid4().hex[:10]}",
            project_id=project_id,
            title=title or "新知识库",
            content=content,
            user_id=user_id,
        )

    def update_project_knowledge(
        self,
        *,
        knowledge_base_id: str = "default",
        project_id: str = DEFAULT_PROJECT_ID,
        title: str = "",
        content: str = "",
        user_id: str = "local",
    ) -> Dict:
        normalized_user_id = str(user_id or "local").strip() or "local"
        normalized_project_id = str(project_id or DEFAULT_PROJECT_ID).strip() or DEFAULT_PROJECT_ID
        project_service.get_project(normalized_project_id, user_id=normalized_user_id)
        normalized_knowledge_id = str(knowledge_base_id or "default").strip() or "default"
        existing = app_db.get_project_knowledge(normalized_knowledge_id, user_id=normalized_user_id)
        existing_created = str(existing.get("created_at", "") or existing.get("updated_at", "") or "").strip()
        existing_project_id = str(existing.get("project_id", "") or DEFAULT_PROJECT_ID)
        if existing_created and existing_project_id != normalized_project_id:
            raise ValueError("Knowledge base already belongs to another project")
        return app_db.upsert_project_knowledge(
            title=str(title or "").strip() or "项目知识库",
            content=str(content or "").strip()[:PROJECT_KNOWLEDGE_LIMIT],
            now_iso=_now_iso(),
            knowledge_id=normalized_knowledge_id,
            project_id=normalized_project_id,
            user_id=normalized_user_id,
        )

    def delete_project_knowledge(
        self,
        knowledge_base_id: str,
        *,
        project_id: str = DEFAULT_PROJECT_ID,
        user_id: str = "local",
    ) -> Dict:
        normalized_user_id = str(user_id or "local").strip() or "local"
        normalized_project_id = str(project_id or DEFAULT_PROJECT_ID).strip() or DEFAULT_PROJECT_ID
        normalized_knowledge_id = str(knowledge_base_id or "").strip()
        if not normalized_knowledge_id:
            raise ValueError("Knowledge base id is required")

        project = project_service.get_project(normalized_project_id, user_id=normalized_user_id)
        existing = app_db.get_project_knowledge(normalized_knowledge_id, user_id=normalized_user_id)
        existing_created = str(existing.get("created_at", "") or existing.get("updated_at", "") or "").strip()
        if not existing_created:
            raise ValueError("Knowledge base not found")
        if str(existing.get("project_id", "") or DEFAULT_PROJECT_ID) != normalized_project_id:
            raise ValueError("Knowledge base does not belong to the selected project")

        deleted = app_db.delete_project_knowledge(normalized_knowledge_id, user_id=normalized_user_id)
        if not deleted:
            raise ValueError("Knowledge base not found")

        remaining = app_db.list_project_knowledge(project_id=normalized_project_id, user_id=normalized_user_id)
        replacement_id = self._repair_project_default_knowledge(project, remaining, normalized_user_id)
        if not remaining:
            replacement_title = f"{str(project.get('title', '') or '项目')}知识库"
            replacement = app_db.upsert_project_knowledge(
                title=replacement_title,
                content="",
                now_iso=_now_iso(),
                knowledge_id=replacement_id,
                project_id=normalized_project_id,
                user_id=normalized_user_id,
            )
            remaining = [replacement]

        return {
            "deleted": True,
            "id": normalized_knowledge_id,
            "project_id": normalized_project_id,
            "replacement_knowledge_base_id": replacement_id,
            "items": remaining,
        }

    def build_effective_project_context(
        self,
        project_context: str,
        knowledge_base_id: str = "default",
        project_id: str = "",
        user_id: str = "local",
    ) -> Dict[str, str]:
        normalized_user_id = str(user_id or "local").strip() or "local"
        normalized_project_id = str(project_id or "").strip()
        normalized_knowledge_base_id = str(knowledge_base_id or "").strip()
        extra_context = str(project_context or "").strip()
        if not normalized_knowledge_base_id:
            return {
                "project_context": extra_context[:PROJECT_CONTEXT_LIMIT],
                "project_context_extra": extra_context[:PROJECT_CONTEXT_LIMIT],
                "knowledge_base_id": "",
                "knowledge_base_title": "",
                "knowledge_base_context": "",
                "knowledge_base_updated_at": "",
            }

        knowledge = self.get_project_knowledge(normalized_knowledge_base_id, user_id=normalized_user_id)
        if normalized_project_id:
            knowledge_project_id = str(knowledge.get("project_id", "") or "default")
            if knowledge_project_id != normalized_project_id:
                raise ValueError("Knowledge base does not belong to the selected project")
        knowledge_content = str(knowledge.get("content", "") or "").strip()

        knowledge_section = (
            f"[项目知识库：长期实体资料 / reusable entity knowledge]\n{knowledge_content}"
            if knowledge_content
            else ""
        )
        extra_section = f"[本次补充事实]\n{extra_context}" if extra_context else ""
        if knowledge_section and extra_section:
            extra_budget = min(len(extra_section), PROJECT_CONTEXT_LIMIT)
            knowledge_budget = max(0, PROJECT_CONTEXT_LIMIT - extra_budget - 2)
            effective_context = "\n\n".join(
                item
                for item in [knowledge_section[:knowledge_budget].strip(), extra_section[:extra_budget].strip()]
                if item
            ).strip()
        else:
            effective_context = (knowledge_section or extra_section).strip()[:PROJECT_CONTEXT_LIMIT]
        return {
            "project_context": effective_context,
            "project_context_extra": extra_context[:PROJECT_CONTEXT_LIMIT],
            "knowledge_base_id": str(knowledge.get("id", "") or "default"),
            "knowledge_base_title": str(knowledge.get("title", "") or "项目知识库"),
            "knowledge_base_context": knowledge_content[:PROJECT_KNOWLEDGE_LIMIT],
            "knowledge_base_updated_at": str(knowledge.get("updated_at", "") or ""),
        }


project_knowledge_service = ProjectKnowledgeService()
