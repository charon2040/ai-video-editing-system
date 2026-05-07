from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    scenario: str = "sports_digest"
    aspect_ratio: str = "16:9"


class AssetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    file_type: str = Field(..., min_length=1, max_length=30)
    file_path: str = ""
    duration_ms: int = 0
    transcript_status: str = "pending"


class TimelineClipInput(BaseModel):
    asset_id: Optional[int] = None
    clip_type: str = "video"
    label: str = ""
    track_type: str = "video"
    track_index: int = 0
    start_ms: int = 0
    end_ms: int = 0
    source_start_ms: int = 0
    source_end_ms: int = 0
    content: str = ""
    dubbing: str = ""
    effects: Dict[str, Any] = Field(default_factory=dict)
    transform: Dict[str, Any] = Field(default_factory=dict)
    transition: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class TimelineClipCreate(TimelineClipInput):
    pass


class TimelineUpdate(BaseModel):
    name: str = "主时间线"
    resolution: str = "1920x1080"
    fps: int = 30
    script: str = ""
    status: str = "draft"
    source_video_path: str = ""
    source_edl_path: str = ""
    render_blueprint: Dict[str, Any] = Field(default_factory=dict)
    clips: List[TimelineClipInput] = Field(default_factory=list)


class TimelineClipPatch(BaseModel):
    clip_type: Optional[str] = None
    track_type: Optional[str] = None
    track_index: Optional[int] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    source_start_ms: Optional[int] = None
    source_end_ms: Optional[int] = None
    label: Optional[str] = None
    content: Optional[str] = None
    dubbing: Optional[str] = None
    effects: Optional[Dict[str, Any]] = None
    transform: Optional[Dict[str, Any]] = None
    transition: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class TimelineClipOrderItem(BaseModel):
    clip_id: int
    track_type: str
    track_index: int = 0
    sort_order: int = 0
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None


class TimelineClipOrderUpdate(BaseModel):
    items: List[TimelineClipOrderItem] = Field(default_factory=list)


class TimelineClipSplit(BaseModel):
    split_ms: int
    keep: str = "both"


class TimelineTransitionApply(BaseModel):
    left_clip_id: int
    right_clip_id: int
    transition_type: str = "fade"
    duration_ms: int = 400
    easing: str = "linear"


class TimelineTransitionClear(BaseModel):
    clip_id: int
    direction: str = "both"


class TimelineClipConcat(BaseModel):
    left_clip_id: int
    right_clip_id: int


class TimelineClipFlip(BaseModel):
    clip_id: int
    enabled: Optional[bool] = None


class TimelineClipNudge(BaseModel):
    clip_id: int
    delta_ms: int = 0


class TimelineClipRippleSplit(BaseModel):
    split_ms: int
    keep: str = "right"


class TimelineTrackCreate(BaseModel):
    track_type: str = "video"
    name: str = ""


class TimelineTrackPatch(BaseModel):
    name: Optional[str] = None
    is_locked: Optional[bool] = None
    is_muted: Optional[bool] = None
    is_visible: Optional[bool] = None


class TimelineTrackOrderUpdate(BaseModel):
    track_ids: List[int] = Field(default_factory=list)


class ExportJobCreate(BaseModel):
    timeline_id: Optional[int] = None
    job_type: str = "preview"
    output_path: str = ""
    source_video_path: str = ""
    render_config: Dict[str, Any] = Field(default_factory=dict)
