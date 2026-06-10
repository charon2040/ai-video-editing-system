from typing import Dict, List


WEB_CUT_ANIMATION_PRESETS: List[Dict] = [
    {"id": "none", "name": "无", "category": "animation", "direction": "both"},
    {"id": "fade", "name": "淡入淡出", "category": "animation", "direction": "both"},
    {"id": "slide_left", "name": "从左滑入", "category": "animation", "direction": "in"},
    {"id": "slide_right", "name": "从右滑入", "category": "animation", "direction": "in"},
    {"id": "slide_top", "name": "从上滑入", "category": "animation", "direction": "in"},
    {"id": "slide_bottom", "name": "从下滑入", "category": "animation", "direction": "in"},
    {"id": "zoom_in", "name": "放大进入", "category": "animation", "direction": "in"},
    {"id": "rotate_in", "name": "旋转进入", "category": "animation", "direction": "in"},
]

WEB_CUT_FILTER_PRESETS: List[Dict] = [
    {"id": "none", "name": "无", "category": "filter", "params": {}},
    {"id": "blur", "name": "模糊", "category": "filter", "params": {"value": 6}},
    {"id": "brightness", "name": "亮度", "category": "filter", "params": {"value": 0.05}},
    {"id": "contrast", "name": "对比度", "category": "filter", "params": {"value": 1.1}},
    {"id": "saturation", "name": "饱和度", "category": "filter", "params": {"value": 1.2}},
    {"id": "grayscale", "name": "黑白", "category": "filter", "params": {}},
    {"id": "sepia", "name": "复古", "category": "filter", "params": {}},
    {"id": "invert", "name": "反色", "category": "filter", "params": {}},
]

WEB_CUT_TRANSITION_PRESETS: List[Dict] = [
    {"id": "fade", "name": "淡化", "category": "transition"},
    {"id": "dissolve", "name": "叠化", "category": "transition"},
    {"id": "dip_black", "name": "黑场", "category": "transition"},
]

TRANSITION_TYPE_ALIASES = {
    "crossfade": "dissolve",
    "fade_black": "dip_black",
    "dipblack": "dip_black",
}


def normalize_transition_type(raw_value: str) -> str:
    value = str(raw_value or "fade").strip().lower()
    value = TRANSITION_TYPE_ALIASES.get(value, value)
    valid_ids = {item["id"] for item in WEB_CUT_TRANSITION_PRESETS}
    return value if value in valid_ids else "fade"


def get_logic_catalog() -> Dict[str, List[Dict]]:
    return {
        "animations": WEB_CUT_ANIMATION_PRESETS,
        "filters": WEB_CUT_FILTER_PRESETS,
        "transitions": WEB_CUT_TRANSITION_PRESETS,
    }
