from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from app.core.config import settings
from app.workflows.schemas import WorkflowTemplate


class WorkflowRegistry:
    def __init__(self) -> None:
        self._templates: Dict[str, WorkflowTemplate] = {}
        self._loaded = False

    @property
    def template_dir(self) -> Path:
        return settings.project_dir / "app" / "workflows" / "templates"

    def _load_templates(self) -> None:
        if self._loaded:
            return
        templates: Dict[str, WorkflowTemplate] = {}
        for path in sorted(self.template_dir.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                template = WorkflowTemplate.model_validate(raw)
            except Exception:
                continue
            if template.enabled and template.id:
                templates[template.id] = template
        self._templates = templates
        self._loaded = True

    def list_templates(self) -> List[Dict]:
        self._load_templates()
        return [template.to_payload() for template in self._templates.values()]

    def get_template(self, template_id: str) -> WorkflowTemplate | None:
        self._load_templates()
        return self._templates.get(str(template_id or "").strip())

    def default_template_id(self) -> str:
        self._load_templates()
        for template in self._templates.values():
            if template.is_default:
                return template.id
        return next(iter(self._templates.keys()), "narration_clip")

    def normalize_template_id(self, template_id: str = "") -> str:
        self._load_templates()
        candidate = str(template_id or "").strip()
        if candidate in self._templates:
            return candidate
        return self.default_template_id()


workflow_registry = WorkflowRegistry()
