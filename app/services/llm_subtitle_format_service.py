from __future__ import annotations

import re
from typing import Any, Dict, List


def normalize_subtitle_text(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalize_subtitles(subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in subtitles or []:
        text = normalize_subtitle_text(item.get("text", ""))
        if not text:
            continue
        try:
            start = int(item.get("start", 0) or 0)
            end = int(item.get("end", 0) or 0)
        except Exception:
            continue
        if end <= start:
            continue
        normalized.append({"start": start, "end": end, "text": text})
    return sorted(normalized, key=lambda value: (int(value["start"]), int(value["end"])))


def subtitle_char_count(subtitles: List[Dict[str, Any]]) -> int:
    return sum(len(str(item.get("text", "") or "")) for item in subtitles or [])


def build_alignment_units(subtitles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    units: List[Dict[str, Any]] = []
    for index, item in enumerate(normalize_subtitles(subtitles), start=1):
        units.append(
            {
                "unit_id": f"unit_{index}",
                "start": int(item.get("start", 0) or 0),
                "end": int(item.get("end", 0) or 0),
                "text": normalize_subtitle_text(item.get("text", "")),
            }
        )
    return units
