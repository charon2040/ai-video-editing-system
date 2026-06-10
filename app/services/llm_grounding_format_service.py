from __future__ import annotations

from typing import Any, Dict, List


def normalize_string_list(
    value: Any,
    *,
    max_items: int = 12,
    max_length: int = 120,
) -> List[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        items = []

    normalized: List[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text:
            continue
        normalized.append(text[:max_length].strip())
        if len(normalized) >= max_items:
            break
    return normalized


def normalize_grounding(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    participants = normalize_string_list(
        payload.get("participants"),
        max_items=8,
        max_length=48,
    )
    uncertain_points = normalize_string_list(
        payload.get("uncertain_points"),
        max_items=10,
        max_length=160,
    )

    side_mappings: List[Dict[str, Any]] = []
    for item in payload.get("side_mappings", []) or []:
        if not isinstance(item, dict):
            continue
        alias = str(item.get("alias", "") or "").strip()
        participant = str(item.get("participant", "") or item.get("resolved_to", "") or "").strip()
        if not alias or not participant:
            continue
        side_mappings.append(
            {
                "alias": alias[:32],
                "participant": participant[:48],
                "confidence": str(item.get("confidence", "") or "").strip()[:16],
                "evidence": normalize_string_list(
                    item.get("evidence"),
                    max_items=3,
                    max_length=80,
                ),
            }
        )
        if len(side_mappings) >= 12:
            break

    entity_mappings: List[Dict[str, Any]] = []
    for item in payload.get("entity_mappings", []) or []:
        if not isinstance(item, dict):
            continue
        entity = str(item.get("entity", "") or "").strip()
        participant = str(item.get("participant", "") or item.get("owner", "") or "").strip()
        if not entity or not participant:
            continue
        entity_mappings.append(
            {
                "entity": entity[:48],
                "participant": participant[:48],
                "relation": str(item.get("relation", "") or item.get("kind", "") or "").strip()[:32],
                "confidence": str(item.get("confidence", "") or "").strip()[:16],
                "evidence": normalize_string_list(
                    item.get("evidence"),
                    max_items=3,
                    max_length=80,
                ),
            }
        )
        if len(entity_mappings) >= 20:
            break

    if not participants and not side_mappings and not entity_mappings and not uncertain_points:
        return {}

    return {
        "participants": participants,
        "side_mappings": side_mappings,
        "entity_mappings": entity_mappings,
        "uncertain_points": uncertain_points,
    }
