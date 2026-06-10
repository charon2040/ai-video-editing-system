from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from app.services import llm_format_service as llm_format


def parse_narration_draft(content: str) -> Dict[str, Any]:
    cleaned = llm_format.clean_content(content)
    try:
        parsed = json.loads(cleaned)
    except Exception as exc:
        raise ValueError("LLM 文案草稿返回格式不是有效 JSON") from exc

    if not isinstance(parsed, dict):
        raise ValueError("LLM 文案草稿必须返回 JSON 对象")

    beats: List[Dict[str, Any]] = []
    if isinstance(parsed.get("beats"), list):
        for index, item in enumerate(parsed.get("beats", []), start=1):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "") or "").strip()
            if not text:
                continue
            beats.append(
                {
                    "id": str(item.get("id", "") or f"beat_{index}"),
                    "title": str(item.get("title", "") or f"第 {index} 段"),
                    "text": text,
                    "order": int(item.get("order", index) or index),
                }
            )

    if not beats:
        raise ValueError("LLM 文案草稿没有返回有效 beats")

    script = str(parsed.get("script", "") or "").strip()
    if not script:
        script = "\n".join(str(item.get("text", "") or "").strip() for item in beats).strip()
    if not script:
        raise ValueError("LLM 文案草稿为空")

    suggestions = []
    if isinstance(parsed.get("suggestions"), list):
        suggestions = [
            str(item).strip()
            for item in parsed.get("suggestions", [])
            if str(item).strip()
        ]

    return {
        "script": script,
        "beats": beats,
        "grounding": llm_format.normalize_grounding(parsed.get("grounding", {}) or {}),
        "suggestions": suggestions,
    }


def _grounding_item_label(item: Dict[str, Any]) -> str:
    parts = [
        str(item.get("alias", "") or item.get("entity", "") or "").strip(),
        str(item.get("participant", "") or "").strip(),
        str(item.get("relation", "") or "").strip(),
    ]
    return " -> ".join(part for part in parts if part) or "未命名事实"


def _grounding_evidence_text(item: Dict[str, Any]) -> str:
    evidence = item.get("evidence", []) if isinstance(item, dict) else []
    if isinstance(evidence, str):
        values = [evidence]
    elif isinstance(evidence, list):
        values = evidence
    else:
        values = []
    return " ".join(str(value or "").strip() for value in values if str(value or "").strip())


def _uses_external_memory(text: str) -> bool:
    return bool(
        re.search(
            r"(模型|自己|自行|外部|常识|记忆|印象|我知道|通常|一般认为).{0,16}(补齐|推断|判断|依据|资料|关系|事实)|"
            r"(external memory|world knowledge|common knowledge)",
            str(text or ""),
            flags=re.IGNORECASE,
        )
    )


def _has_task_specific_evidence(evidence_text: str) -> bool:
    return bool(
        re.search(
            r"(用户要求|需求|本次补充事实|本次任务|本次视频|本视频|原始字幕|字幕|ASR|subtitle|subtitles|requirements)",
            str(evidence_text or ""),
            flags=re.IGNORECASE,
        )
    )


def _uses_long_term_knowledge_only(evidence_text: str) -> bool:
    text = str(evidence_text or "")
    has_long_term_context = bool(
        re.search(
            r"(项目知识库|长期实体资料|长期资料|知识库|稳定关系|别名|成员关系|术语|project knowledge|knowledge base)",
            text,
            flags=re.IGNORECASE,
        )
    )
    return has_long_term_context and not _has_task_specific_evidence(text)


def _relation_is_task_specific(relation: str) -> bool:
    return bool(
        re.search(
            r"(本次|本视频|当前|现场|片中|画面中|这段|此处|方位|左右|位置|身份|角色|归属|行动|动作|状态|"
            r"current|this_video|this_task|in_video|scene|position|side|role|owner|ownership|action|state)",
            str(relation or ""),
            flags=re.IGNORECASE,
        )
    )


def _normalize_fact_value(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


def _is_uncertain_confidence(confidence: str) -> bool:
    return bool(
        re.search(
            r"(low|uncertain|unknown|不确定|存疑|低|弱|待确认)",
            str(confidence or ""),
            flags=re.IGNORECASE,
        )
    )


def _relation_bucket(relation: str) -> str:
    text = str(relation or "")
    if re.search(
        r"(ban|banned|block|deny|禁用|封锁|按掉|ban掉)",
        text,
        flags=re.IGNORECASE,
    ):
        return "blocked"
    if re.search(
        r"(归属|拥有|使用|选用|选择|拿到|抢到|锁下|拿出|祭出|属于|"
        r"owner|ownership|belongs|use|uses|used|pick|picked|select|selected|choose|chosen)",
        text,
        flags=re.IGNORECASE,
    ):
        return "owned_or_used"
    if _relation_is_task_specific(text):
        return "task_specific"
    return ""


def _draft_participants(grounding: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for item in grounding.get("participants", []) or []:
        text = str(item or "").strip()
        if text:
            values.append(text)
    for collection in ("side_mappings", "entity_mappings"):
        for item in grounding.get(collection, []) or []:
            if not isinstance(item, dict):
                continue
            text = str(item.get("participant", "") or "").strip()
            if text:
                values.append(text)
    return list(dict.fromkeys(values))


def _draft_entities(grounding: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for item in grounding.get("entity_mappings", []) or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("entity", "") or "").strip()
        if text:
            values.append(text)
    return list(dict.fromkeys(values))


def _escape_for_loose_regex(value: str) -> str:
    return re.escape(str(value or "").strip())


def _text_claims_entity_for_participant(clause: str, participant: str, entity: str) -> bool:
    if not participant or not entity:
        return False
    participant_pattern = _escape_for_loose_regex(participant)
    entity_pattern = _escape_for_loose_regex(entity)
    ownership_markers = (
        r"(抢到|选出|选到|选用|选择|锁下|拿到|拿出|祭出|使用|用出|给到|归属|属于|"
        r"阵容|则是|则为|则选择|pick|picked|select|selected|choose|chosen|use|used|uses)"
    )
    return bool(
        re.search(
            rf"{participant_pattern}[^，,。！？；;\n]{{0,24}}{ownership_markers}[^，,。！？；;\n]{{0,24}}{entity_pattern}",
            clause,
            flags=re.IGNORECASE,
        )
        or re.search(
            rf"{entity_pattern}[^，,。！？；;\n]{{0,24}}(归属|属于|给到|交给|被|由|为)[^，,。！？；;\n]{{0,24}}{participant_pattern}",
            clause,
            flags=re.IGNORECASE,
        )
    )


def _draft_text_self_consistency_issues(draft: Dict[str, Any], grounding: Dict[str, Any]) -> List[str]:
    participants = _draft_participants(grounding)
    entities = _draft_entities(grounding)
    if len(participants) < 2 or not entities:
        return []

    script = str(draft.get("script", "") or "")
    beats_text = "\n".join(
        str(item.get("text", "") or "")
        for item in draft.get("beats", []) or []
        if isinstance(item, dict)
    )
    text = f"{script}\n{beats_text}"
    clauses = [
        clause.strip()
        for clause in re.split(r"[，,。！？；;\n]+", text)
        if clause.strip()
    ]

    issues: List[str] = []
    for entity in entities:
        owners: List[str] = []
        for participant in participants:
            if any(
                _text_claims_entity_for_participant(clause, participant, entity)
                for clause in clauses
            ):
                owners.append(participant)
        owners = list(dict.fromkeys(owners))
        if len(owners) > 1:
            issues.append(
                f"正文自相矛盾：实体“{entity}”被确定性写成属于/被选择/被使用于多个参与方（{', '.join(owners[:4])}）。"
            )
    return issues


def draft_self_consistency_issues(draft: Dict[str, Any]) -> List[str]:
    grounding = draft.get("grounding", {}) or {}
    issues: List[str] = []

    side_owner: Dict[str, str] = {}
    for item in grounding.get("side_mappings", []) or []:
        if not isinstance(item, dict):
            continue
        alias = _normalize_fact_value(item.get("alias", ""))
        participant = _normalize_fact_value(item.get("participant", ""))
        confidence = str(item.get("confidence", "") or "")
        if not alias or not participant or _is_uncertain_confidence(confidence):
            continue
        previous = side_owner.get(alias)
        if previous and previous != participant:
            issues.append(
                f"grounding.side_mappings 自相矛盾：“{item.get('alias')}”同时指向多个参与方。"
            )
            continue
        side_owner[alias] = participant

    entity_owner: Dict[tuple[str, str], str] = {}
    for item in grounding.get("entity_mappings", []) or []:
        if not isinstance(item, dict):
            continue
        entity = _normalize_fact_value(item.get("entity", ""))
        participant = _normalize_fact_value(item.get("participant", ""))
        relation = str(item.get("relation", "") or "")
        confidence = str(item.get("confidence", "") or "")
        bucket = _relation_bucket(relation)
        if not entity or not participant or not bucket or _is_uncertain_confidence(confidence):
            continue
        key = (entity, bucket)
        previous = entity_owner.get(key)
        if previous and previous != participant:
            issues.append(
                f"grounding.entity_mappings 自相矛盾：“{item.get('entity')}”在“{bucket}”关系里同时指向多个参与方。"
            )
            continue
        entity_owner[key] = participant

    issues.extend(_draft_text_self_consistency_issues(draft, grounding))
    return list(dict.fromkeys(issues))


def draft_grounding_contract_issues(draft: Dict[str, Any]) -> List[str]:
    script = str(draft.get("script", "") or "")
    beats_text = "\n".join(
        str(item.get("text", "") or "")
        for item in draft.get("beats", []) or []
        if isinstance(item, dict)
    )
    text = f"{script}\n{beats_text}"
    grounding = draft.get("grounding", {}) or {}
    side_mappings = grounding.get("side_mappings", []) or []
    entity_mappings = grounding.get("entity_mappings", []) or []
    uncertain_text = " ".join(str(item or "") for item in grounding.get("uncertain_points", []) or [])

    issues: List[str] = []
    if _uses_external_memory(text + "\n" + uncertain_text):
        issues.append("正文或 grounding 使用了模型外部记忆补齐事实，必须只依据用户要求、项目知识库、本次补充事实和原始字幕。")

    for item in side_mappings:
        if not isinstance(item, dict):
            continue
        evidence_text = _grounding_evidence_text(item)
        label = _grounding_item_label(item)
        if not evidence_text:
            issues.append(f"grounding.side_mappings 中的“{label}”缺少 evidence。")
            continue
        if _uses_external_memory(evidence_text):
            issues.append(f"grounding.side_mappings 中的“{label}”使用了外部记忆或常识。")
        if not _has_task_specific_evidence(evidence_text):
            issues.append(f"grounding.side_mappings 中的“{label}”属于本次视频方位/位置事实，必须提供用户要求、本次补充事实或原始字幕证据。")

    for item in entity_mappings:
        if not isinstance(item, dict):
            continue
        evidence_text = _grounding_evidence_text(item)
        relation = str(item.get("relation", "") or "").strip()
        label = _grounding_item_label(item)
        if not evidence_text:
            issues.append(f"grounding.entity_mappings 中的“{label}”缺少 evidence。")
            continue
        if _uses_external_memory(evidence_text + " " + relation):
            issues.append(f"grounding.entity_mappings 中的“{label}”使用了外部记忆或常识。")
        if _relation_is_task_specific(relation) and not _has_task_specific_evidence(evidence_text):
            issues.append(f"grounding.entity_mappings 中的“{label}”是本次视频事实，必须提供用户要求、本次补充事实或原始字幕证据。")
        if _relation_is_task_specific(relation) and _uses_long_term_knowledge_only(evidence_text):
            issues.append(f"grounding.entity_mappings 中的“{label}”把长期知识库当成本次视频事实证据。")

    return list(dict.fromkeys(issues))


def draft_atomicity_issues(draft: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    beats = draft.get("beats", []) or []
    transition_pattern = re.compile(
        r"(随后|接着|紧接着|与此同时|同时|好在|随即|此后|之后|然后|直到|最后|最终|然而|不过|另一方面|转而|接下来)"
    )
    phase_pattern = re.compile(r"(BP|前期|中期|后期|龙魂团|远古龙团|赛后|复盘|推进|结束比赛)")

    for index, item in enumerate(beats, start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "") or f"第 {index} 段").strip()
        text = str(item.get("text", "") or "").strip()
        compact_len = len("".join(text.split()))
        transitions = transition_pattern.findall(text)
        phases = list(dict.fromkeys(phase_pattern.findall(text)))

        if compact_len > 260:
            issues.append(
                f"第 {index} 段“{title}”约 {compact_len} 字，过长，容易覆盖多个不连续素材窗口，请拆成更小的连续事件 beat。"
            )
            continue

        if compact_len > 160 and len(transitions) >= 3:
            issues.append(
                f"第 {index} 段“{title}”包含多个转场词（{', '.join(transitions[:4])}），疑似把多个事件揉在一起，请按时间顺序拆分。"
            )
            continue

        if compact_len > 140 and len(phases) >= 4:
            issues.append(
                f"第 {index} 段“{title}”同时覆盖多个阶段（{', '.join(phases[:4])}），请拆成单一连续事件。"
            )

    return list(dict.fromkeys(issues))


def _compact_text_len(text: str) -> int:
    return len(re.sub(r"\s+", "", str(text or "")))


def draft_length_issues(
    draft: Dict[str, Any],
    *,
    duration_seconds: int = 0,
    length_guidance: Dict[str, Any] | None = None,
) -> List[str]:
    guidance = length_guidance or {}
    beats = [
        item
        for item in draft.get("beats", []) or []
        if isinstance(item, dict) and str(item.get("text", "") or "").strip()
    ]
    if not beats:
        return ["文案没有有效 beat。"]

    issues: List[str] = []
    total_text = "\n".join(str(item.get("text", "") or "").strip() for item in beats)
    total_chars = _compact_text_len(total_text)
    target_min = int(guidance.get("target_total_chars_min", 0) or 0)
    target_max = int(guidance.get("target_total_chars_max", 0) or 0)
    beat_min = int(guidance.get("preferred_beat_count_min", 0) or 0)
    beat_max = int(guidance.get("preferred_beat_count_max", 0) or 0)
    per_beat_min = int(guidance.get("preferred_beat_chars_min", 0) or 0)
    has_target_duration = int(duration_seconds or 0) > 0

    if target_min and total_chars < int(target_min * 0.9):
        issues.append(
            f"整稿约 {total_chars} 字，明显短于目标下限 {target_min} 字；当前像提纲摘要，需要扩成正式配音稿。"
        )
    if target_max and total_chars > int(target_max * 1.25):
        issues.append(
            f"整稿约 {total_chars} 字，明显超过目标上限 {target_max} 字；请压缩冗余铺垫但保留关键事件。"
        )

    if beat_min and len(beats) < beat_min:
        issues.append(
            f"当前只有 {len(beats)} 个 beat，少于建议下限 {beat_min}；请按真实时间顺序补足关键连续事件。"
        )
    if beat_max and len(beats) > beat_max + 2:
        issues.append(
            f"当前有 {len(beats)} 个 beat，明显多于建议上限 {beat_max}；请合并同一连续事件里的碎片段落。"
        )

    if has_target_duration and per_beat_min:
        short_items: List[str] = []
        for index, item in enumerate(beats, start=1):
            text = str(item.get("text", "") or "").strip()
            title = str(item.get("title", "") or f"第 {index} 段").strip()
            compact_len = _compact_text_len(text)
            is_edge = index == 1 or index == len(beats)
            threshold = int(per_beat_min * (0.55 if is_edge else 0.75))
            if compact_len < threshold:
                short_items.append(f"第 {index} 段“{title}”约 {compact_len} 字")
        if short_items and len(short_items) >= max(2, len(beats) // 3):
            issues.append(
                "多个 beat 过短，容易变成剧情梗概而不是配音文案："
                + "；".join(short_items[:5])
                + "。请补足背景、动作、结果和局势影响。"
            )

    return list(dict.fromkeys(issues))


def draft_validation_issues(
    draft: Dict[str, Any],
    *,
    duration_seconds: int = 0,
    length_guidance: Dict[str, Any] | None = None,
) -> List[str]:
    return list(
        dict.fromkeys(
            [
                *draft_self_consistency_issues(draft),
                *draft_grounding_contract_issues(draft),
                *draft_atomicity_issues(draft),
                *draft_length_issues(
                    draft,
                    duration_seconds=duration_seconds,
                    length_guidance=length_guidance,
                ),
            ]
        )
    )
