import logging

from fastapi import APIRouter, HTTPException

from app.schemas.studio import (
    TimelineClipConcat,
    TimelineClipCreate,
    TimelineClipFlip,
    TimelineClipNudge,
    TimelineClipOrderUpdate,
    TimelineClipPatch,
    TimelineClipRippleSplit,
    TimelineClipSplit,
    TimelineTrackCreate,
    TimelineTrackOrderUpdate,
    TimelineTrackPatch,
    TimelineTransitionApply,
    TimelineTransitionClear,
    TimelineUpdate,
)
from app.services.editor_timeline_service import editor_timeline_service

from .common import ensure_project

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/projects/{project_id}/timeline")
async def get_project_timeline(project_id: int):
    ensure_project(project_id)
    return editor_timeline_service.get_project_timeline(project_id)


@router.get("/projects/{project_id}/timeline/history")
async def get_project_timeline_history_state(project_id: int):
    ensure_project(project_id)
    return editor_timeline_service.get_timeline_history_state(project_id)


@router.post("/projects/{project_id}/timeline/history/undo")
async def undo_project_timeline(project_id: int):
    ensure_project(project_id)
    return editor_timeline_service.undo_timeline(project_id)


@router.post("/projects/{project_id}/timeline/history/redo")
async def redo_project_timeline(project_id: int):
    ensure_project(project_id)
    return editor_timeline_service.redo_timeline(project_id)


@router.post("/projects/{project_id}/timeline/history/recover")
async def recover_project_timeline_history(project_id: int):
    ensure_project(project_id)
    return editor_timeline_service.recover_timeline_history(project_id)


@router.post("/projects/{project_id}/timeline/clear")
async def clear_project_timeline(project_id: int):
    ensure_project(project_id)
    return editor_timeline_service.clear_timeline_clips(project_id)


@router.put("/projects/{project_id}/timeline")
async def update_project_timeline(project_id: int, payload: TimelineUpdate):
    ensure_project(project_id)
    return editor_timeline_service.upsert_timeline(project_id, payload.model_dump())


@router.patch("/projects/{project_id}/timeline/clips/{clip_id}")
async def patch_project_timeline_clip(project_id: int, clip_id: int, payload: TimelineClipPatch):
    ensure_project(project_id)
    clip = editor_timeline_service.update_timeline_clip(project_id, clip_id, payload.model_dump(exclude_unset=True))
    if not clip:
        raise HTTPException(status_code=404, detail="Timeline clip not found")
    return clip


@router.post("/projects/{project_id}/timeline/clips")
async def create_project_timeline_clip(project_id: int, payload: TimelineClipCreate):
    ensure_project(project_id)
    clip = editor_timeline_service.create_timeline_clip(project_id, payload.model_dump())
    if not clip:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return clip


@router.post("/projects/{project_id}/timeline/tracks")
async def create_project_timeline_track(project_id: int, payload: TimelineTrackCreate):
    ensure_project(project_id)
    track = editor_timeline_service.create_timeline_track(project_id, payload.model_dump())
    if not track:
        raise HTTPException(status_code=404, detail="Timeline not found")
    return track


@router.delete("/projects/{project_id}/timeline/tracks/{track_id}")
async def delete_project_timeline_track(project_id: int, track_id: int):
    ensure_project(project_id)
    deleted = editor_timeline_service.delete_timeline_track(project_id, track_id)
    if not deleted:
        raise HTTPException(status_code=400, detail="Track not found or still has clips")
    return {"status": "success"}


@router.patch("/projects/{project_id}/timeline/tracks/{track_id}")
async def patch_project_timeline_track(project_id: int, track_id: int, payload: TimelineTrackPatch):
    ensure_project(project_id)
    track = editor_timeline_service.update_timeline_track(project_id, track_id, payload.model_dump(exclude_unset=True))
    if not track:
        raise HTTPException(status_code=404, detail="Timeline track not found")
    return track


@router.post("/projects/{project_id}/timeline/tracks/reorder")
async def reorder_project_timeline_tracks(project_id: int, payload: TimelineTrackOrderUpdate):
    ensure_project(project_id)
    return editor_timeline_service.reorder_timeline_tracks(project_id, payload.model_dump())


@router.delete("/projects/{project_id}/timeline/clips/{clip_id}")
async def delete_project_timeline_clip(project_id: int, clip_id: int):
    ensure_project(project_id)
    logger.info("[TimelineDelete] request project_id=%s clip_id=%s", project_id, clip_id)
    deleted = editor_timeline_service.delete_timeline_clip(project_id, clip_id)
    if not deleted:
        logger.warning("[TimelineDelete] failed project_id=%s clip_id=%s", project_id, clip_id)
        raise HTTPException(status_code=404, detail="Timeline clip not found")
    logger.info("[TimelineDelete] success project_id=%s clip_id=%s", project_id, clip_id)
    return {"status": "success"}


@router.post("/projects/{project_id}/timeline/clips/{clip_id}/split")
async def split_project_timeline_clip(project_id: int, clip_id: int, payload: TimelineClipSplit):
    ensure_project(project_id)
    keep = str(payload.keep or "both").lower()
    if keep not in {"left", "right", "both"}:
        raise HTTPException(status_code=400, detail="Invalid keep mode")
    timeline = editor_timeline_service.split_timeline_clip(project_id=project_id, clip_id=clip_id, split_ms=int(payload.split_ms), keep=keep)
    if not timeline:
        raise HTTPException(status_code=404, detail="Timeline clip not found or split out of range")
    return timeline


@router.post("/projects/{project_id}/timeline/clips/{clip_id}/separate_audio")
async def separate_audio_from_project_timeline_clip(project_id: int, clip_id: int):
    ensure_project(project_id)
    result = editor_timeline_service.separate_audio_from_timeline_clip(project_id, clip_id)
    if not result:
        raise HTTPException(status_code=400, detail="Separate audio failed")
    return result


@router.post("/projects/{project_id}/timeline/transitions")
async def apply_project_timeline_transition(project_id: int, payload: TimelineTransitionApply):
    ensure_project(project_id)
    timeline = editor_timeline_service.apply_timeline_transition(project_id, payload.model_dump())
    if not timeline:
        raise HTTPException(status_code=400, detail="Apply transition failed")
    return timeline


@router.delete("/projects/{project_id}/timeline/transitions")
async def clear_project_timeline_transition(project_id: int, payload: TimelineTransitionClear):
    ensure_project(project_id)
    timeline = editor_timeline_service.clear_timeline_transition(project_id, payload.model_dump())
    if not timeline:
        raise HTTPException(status_code=400, detail="Clear transition failed")
    return timeline


@router.post("/projects/{project_id}/timeline/clips/concat")
async def concat_project_timeline_clips(project_id: int, payload: TimelineClipConcat):
    ensure_project(project_id)
    timeline = editor_timeline_service.concat_timeline_clips(project_id, payload.model_dump())
    if not timeline:
        raise HTTPException(status_code=400, detail="Concat clips failed")
    return timeline


@router.post("/projects/{project_id}/timeline/clips/flip_h")
async def flip_project_timeline_clip_h(project_id: int, payload: TimelineClipFlip):
    ensure_project(project_id)
    timeline = editor_timeline_service.set_clip_flip_h(project_id, payload.model_dump())
    if not timeline:
        raise HTTPException(status_code=400, detail="Toggle flip failed")
    return timeline


@router.post("/projects/{project_id}/timeline/clips/{clip_id}/ripple_delete")
async def ripple_delete_project_timeline_clip(project_id: int, clip_id: int):
    ensure_project(project_id)
    timeline = editor_timeline_service.ripple_delete_timeline_clip(project_id, clip_id)
    if not timeline:
        raise HTTPException(status_code=400, detail="Ripple delete failed")
    return timeline


@router.post("/projects/{project_id}/timeline/clips/{clip_id}/ripple_split")
async def ripple_split_project_timeline_clip(project_id: int, clip_id: int, payload: TimelineClipRippleSplit):
    ensure_project(project_id)
    keep = str(payload.keep or "right").lower()
    if keep not in {"left", "right"}:
        raise HTTPException(status_code=400, detail="Invalid keep mode")
    timeline = editor_timeline_service.ripple_split_timeline_clip(project_id=project_id, clip_id=clip_id, split_ms=int(payload.split_ms), keep=keep)
    if not timeline:
        raise HTTPException(status_code=400, detail="Ripple split failed")
    return timeline


@router.post("/projects/{project_id}/timeline/clips/nudge")
async def nudge_project_timeline_clip(project_id: int, payload: TimelineClipNudge):
    ensure_project(project_id)
    timeline = editor_timeline_service.nudge_timeline_clip(project_id, payload.model_dump())
    if not timeline:
        raise HTTPException(status_code=400, detail="Nudge clip failed")
    return timeline


@router.post("/projects/{project_id}/timeline/clips/ripple_insert")
async def ripple_insert_project_timeline_clip(project_id: int, payload: TimelineClipCreate):
    ensure_project(project_id)
    timeline = editor_timeline_service.ripple_insert_timeline_clip(project_id, payload.model_dump())
    if not timeline:
        raise HTTPException(status_code=400, detail="Ripple insert failed")
    return timeline


@router.post("/projects/{project_id}/timeline/reorder")
async def reorder_project_timeline_clips(project_id: int, payload: TimelineClipOrderUpdate):
    ensure_project(project_id)
    return editor_timeline_service.reorder_timeline_clips(project_id, payload.model_dump())
