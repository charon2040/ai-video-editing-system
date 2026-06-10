from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings
from app.services import llm_draft_service as llm_draft
from app.services import llm_format_service as llm_format
from app.services import llm_prompt_service as llm_prompts


logger = logging.getLogger(__name__)


def _draft_length_guidance(duration_seconds: int, raw_char_count: int, style: str = "") -> Dict[str, Any]:
    duration = max(0, int(duration_seconds or 0))
    raw_chars = max(0, int(raw_char_count or 0))
    normalized_style = str(style or "").strip().lower()

    if duration > 0:
        min_rate = max(1.0, float(settings.narration_chars_per_second_min or 3.2))
        max_rate = max(min_rate + 0.5, float(settings.narration_chars_per_second_max or 5.2))
        min_chars = max(80, int(duration * min_rate))
        max_chars = max(min_chars + 40, int(duration * max_rate))
        if normalized_style == "short_hook":
            min_chars = max(70, int(min_chars * 0.85))
            max_chars = max(min_chars + 40, int(max_chars * 0.9))
        elif normalized_style in {"analysis", "highlight"}:
            min_chars = int(min_chars * 1.08)
            max_chars = int(max_chars * 1.12)

        if duration <= 45:
            beat_range = [3, 5]
            per_beat = [35, 90]
        elif duration <= 75:
            beat_range = [4, 7]
            per_beat = [55, 120]
        elif duration <= 120:
            beat_range = [6, 9]
            per_beat = [70, 150]
        else:
            beat_range = [8, 12]
            per_beat = [80, 170]
    else:
        min_chars, max_chars = 0, 0
        if raw_chars >= 10000:
            beat_range = [6, 10]
        elif raw_chars >= 5000:
            beat_range = [5, 8]
        else:
            beat_range = [4, 7]
        if normalized_style == "short_hook":
            beat_range = [3, 6]
        per_beat = [70, 160]

    return {
        "duration_seconds": duration,
        "raw_char_count": raw_chars,
        "target_total_chars_min": min_chars,
        "target_total_chars_max": max_chars,
        "preferred_beat_count_min": beat_range[0],
        "preferred_beat_count_max": beat_range[1],
        "preferred_beat_chars_min": per_beat[0],
        "preferred_beat_chars_max": per_beat[1],
        "note": "目标时长存在时按可配置语速估算文案长度；duration_seconds 为 0 表示自动长度，不设置固定总字数，只要求不要退化成提纲或短摘要。",
    }


def _request_narration_draft(
    client: OpenAI,
    *,
    system_prompt: str,
    user_content: str,
    request_timeout: float,
) -> Dict[str, Any]:
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
        timeout=request_timeout,
    )
    content = response.choices[0].message.content or ""
    logger.info("LLM narration draft response received: chars=%s", len(content))
    return llm_draft.parse_narration_draft(content)


def _repair_narration_draft(
    client: OpenAI,
    *,
    requirements: str,
    project_context: str,
    subtitles: List[Dict[str, Any]],
    duration_seconds: int,
    style: str,
    previous_draft: Dict[str, Any],
    validation_issues: List[str],
    request_timeout: float,
) -> Dict[str, Any]:
    raw_char_count = llm_format.subtitle_char_count(subtitles)
    length_guidance = _draft_length_guidance(duration_seconds, raw_char_count, style)
    user_content = json.dumps(
        {
            "requirements": requirements,
            "project_context": project_context,
            "duration_seconds": int(duration_seconds or 0),
            "style": style,
            "validation_issues": validation_issues,
            "previous_draft": previous_draft,
            "subtitle_count": len(subtitles),
            "raw_char_count": raw_char_count,
            "draft_length_guidance": length_guidance,
            "subtitles": subtitles,
        },
        ensure_ascii=False,
    )
    return _request_narration_draft(
        client,
        system_prompt=llm_prompts.NARRATION_REPAIR_PROMPT,
        user_content=user_content,
        request_timeout=request_timeout,
    )


def generate_narration_draft(
    client: OpenAI,
    requirements: str,
    subtitles: List[Dict[str, Any]],
    duration_seconds: int = 0,
    style: str = "",
    project_context: str = "",
) -> Dict[str, Any]:
    text = str(requirements or "").strip()
    if not text:
        raise RuntimeError("缺少用户剪辑要求，无法生成文案草稿。")

    normalized_subtitles = llm_format.normalize_subtitles(subtitles)
    if not normalized_subtitles:
        raise RuntimeError("ASR 字幕为空，无法生成文案草稿。")

    raw_char_count = llm_format.subtitle_char_count(normalized_subtitles)
    length_guidance = _draft_length_guidance(duration_seconds, raw_char_count, style)

    user_content = json.dumps(
        {
            "requirements": text,
            "project_context": str(project_context or "").strip()[:12000],
            "duration_seconds": int(duration_seconds or 0),
            "style": style,
            "subtitle_count": len(normalized_subtitles),
            "raw_char_count": raw_char_count,
            "draft_length_guidance": length_guidance,
            "subtitles": normalized_subtitles,
        },
        ensure_ascii=False,
    )

    try:
        request_timeout = max(float(settings.llm_timeout_seconds), 240.0)
        logger.info(
            "LLM narration draft request: model=%s timeout=%ss requirement_chars=%s subtitle_count=%s raw_chars=%s",
            settings.llm_model,
            request_timeout,
            len(text),
            len(normalized_subtitles),
            raw_char_count,
        )
        draft = _request_narration_draft(
            client,
            system_prompt=llm_prompts.NARRATION_DRAFT_PROMPT,
            user_content=user_content,
            request_timeout=request_timeout,
        )
        validation_issues = llm_draft.draft_validation_issues(
            draft,
            duration_seconds=duration_seconds,
            length_guidance=length_guidance,
        )
        if not validation_issues:
            return draft

        logger.warning(
            "LLM narration draft validation failed, repairing once: %s",
            validation_issues,
        )
        repaired = _repair_narration_draft(
            client,
            requirements=text,
            project_context=str(project_context or "").strip()[:12000],
            subtitles=normalized_subtitles,
            duration_seconds=duration_seconds,
            style=style,
            previous_draft=draft,
            validation_issues=validation_issues,
            request_timeout=request_timeout,
        )
        repaired_issues = llm_draft.draft_validation_issues(
            repaired,
            duration_seconds=duration_seconds,
            length_guidance=length_guidance,
        )
        if repaired_issues:
            raise RuntimeError(
                "LLM 文案草稿校验失败："
                + "；".join(repaired_issues)
                + "。请把用户要求写得更明确，或在本次补充事实里补充关键事实后重试。"
            )
        return repaired
    except Exception as exc:
        logger.warning("LLM narration draft failed from raw subtitles: %s", exc)
        raise RuntimeError(f"LLM 文案草稿生成失败：{exc}") from exc
