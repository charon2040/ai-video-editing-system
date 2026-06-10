from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List

from app.domain.schemas import build_script_from_beats, normalize_draft_beats
from app.services.llm_service import llm_service


@dataclass(frozen=True)
class DraftWorkflowResult:
    script: str
    beats: List[Dict[str, Any]]
    grounding: Dict[str, Any] = field(default_factory=dict)
    suggestions: List[Any] = field(default_factory=list)

    @property
    def voiceover_script(self) -> str:
        return build_script_from_beats(self.beats)


class DraftWorkflowService:
    def _split_long_text(self, text: str, *, max_chars: int = 180) -> List[str]:
        normalized = re.sub(r"\s+", " ", str(text or "")).strip()
        if not normalized:
            return []

        sentences = [
            item.strip()
            for item in re.split(r"(?<=[。！？!?；;])\s*", normalized)
            if item.strip()
        ]
        if not sentences:
            sentences = [normalized]

        chunks: List[str] = []
        current = ""
        for sentence in sentences:
            if len(sentence) > max_chars:
                if current:
                    chunks.append(current.strip())
                    current = ""
                subparts = [
                    item.strip()
                    for item in re.split(r"(?<=[，,、])\s*", sentence)
                    if item.strip()
                ] or [sentence]
                for part in subparts:
                    if current and len(current) + len(part) > max_chars:
                        chunks.append(current.strip())
                        current = part
                    else:
                        current = f"{current}{part}" if current else part
                continue

            if current and len(current) + len(sentence) > max_chars:
                chunks.append(current.strip())
                current = sentence
            else:
                current = f"{current}{sentence}" if current else sentence

        if current.strip():
            chunks.append(current.strip())
        return chunks or [normalized]

    def _script_to_beats(self, script: str) -> List[Dict[str, Any]]:
        normalized = str(script or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        paragraphs = [
            re.sub(r"\s+", " ", item).strip()
            for item in re.split(r"\n\s*\n+", normalized)
            if item.strip()
        ]
        if len(paragraphs) <= 1:
            paragraphs = self._split_long_text(normalized)

        beats: List[Dict[str, Any]] = []
        for index, paragraph in enumerate(paragraphs, start=1):
            text = str(paragraph or "").strip()
            if not text:
                continue
            beats.append(
                {
                    "id": f"beat_{index}",
                    "title": f"第 {index} 段",
                    "text": text,
                    "order": index,
                }
            )
        return normalize_draft_beats(beats)

    def build_script_match_draft(self, *, script: str) -> DraftWorkflowResult:
        draft_script = str(script or "").strip()
        draft_beats = self._script_to_beats(draft_script)
        if not draft_beats and draft_script:
            draft_beats = normalize_draft_beats(
                [{"id": "beat_1", "title": "第 1 段", "text": draft_script, "order": 1}]
            )
        return DraftWorkflowResult(
            script=draft_script or build_script_from_beats(draft_beats),
            beats=draft_beats,
            grounding={
                "mode": "script_match",
                "source": "user_script",
                "fact_policy": "preserve_user_text_without_llm_rewrite",
            },
            suggestions=["定稿文案匹配模式：系统只拆分文案并匹配素材，不会改写正文。"],
        )

    def generate_narration_draft(
        self,
        *,
        request_text: str,
        subtitles: List[Dict[str, Any]],
        duration_seconds: int,
        style: str,
        project_context: str,
    ) -> DraftWorkflowResult:
        draft = llm_service.generate_narration_draft(
            request_text,
            subtitles,
            duration_seconds=duration_seconds,
            style=style,
            project_context=project_context,
        )
        draft_beats = normalize_draft_beats(draft.get("beats", []))
        draft_script = (
            str(draft.get("script", "") or request_text or "").strip()
            or build_script_from_beats(draft_beats)
        )
        if not draft_beats and draft_script:
            draft_beats = normalize_draft_beats(
                [{"id": "beat_1", "title": "第 1 段", "text": draft_script, "order": 1}]
            )

        return DraftWorkflowResult(
            script=draft_script,
            beats=draft_beats,
            grounding=draft.get("grounding", {}) or {},
            suggestions=draft.get("suggestions", []) or [],
        )


draft_workflow_service = DraftWorkflowService()
