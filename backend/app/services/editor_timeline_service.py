from typing import Dict, Optional

from app.services.studio_service import studio_service


class EditorTimelineService:
    def get_project_timeline(self, project_id: int) -> Optional[Dict]:
        return studio_service.get_project_timeline(project_id)

    def get_timeline_history_state(self, project_id: int) -> Dict:
        return studio_service.get_timeline_history_state(project_id)

    def undo_timeline(self, project_id: int) -> Dict:
        return studio_service.undo_timeline(project_id)

    def redo_timeline(self, project_id: int) -> Dict:
        return studio_service.redo_timeline(project_id)

    def recover_timeline_history(self, project_id: int) -> Dict:
        return studio_service.recover_timeline_history(project_id)

    def clear_timeline_clips(self, project_id: int) -> Dict:
        return studio_service.clear_timeline_clips(project_id)

    def upsert_timeline(self, project_id: int, payload: Dict) -> Dict:
        return studio_service.upsert_timeline(project_id, payload)

    def update_timeline_clip(self, project_id: int, clip_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.update_timeline_clip(project_id, clip_id, payload)

    def create_timeline_clip(self, project_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.create_timeline_clip(project_id, payload)

    def create_timeline_track(self, project_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.create_timeline_track(project_id, payload)

    def delete_timeline_track(self, project_id: int, track_id: int) -> bool:
        return studio_service.delete_timeline_track(project_id, track_id)

    def update_timeline_track(self, project_id: int, track_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.update_timeline_track(project_id, track_id, payload)

    def reorder_timeline_tracks(self, project_id: int, payload: Dict) -> Dict:
        return studio_service.reorder_timeline_tracks(project_id, payload)

    def delete_timeline_clip(self, project_id: int, clip_id: int) -> bool:
        return studio_service.delete_timeline_clip(project_id, clip_id)

    def split_timeline_clip(self, project_id: int, clip_id: int, split_ms: int, keep: str) -> Optional[Dict]:
        return studio_service.split_timeline_clip(project_id, clip_id, split_ms, keep)

    def separate_audio_from_timeline_clip(self, project_id: int, clip_id: int) -> Optional[Dict]:
        return studio_service.separate_audio_from_timeline_clip(project_id, clip_id)

    def apply_timeline_transition(self, project_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.apply_timeline_transition(project_id, payload)

    def clear_timeline_transition(self, project_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.clear_timeline_transition(project_id, payload)

    def concat_timeline_clips(self, project_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.concat_timeline_clips(project_id, payload)

    def set_clip_flip_h(self, project_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.set_clip_flip_h(project_id, payload)

    def ripple_delete_timeline_clip(self, project_id: int, clip_id: int) -> Optional[Dict]:
        return studio_service.ripple_delete_timeline_clip(project_id, clip_id)

    def ripple_split_timeline_clip(self, project_id: int, clip_id: int, split_ms: int, keep: str) -> Optional[Dict]:
        return studio_service.ripple_split_timeline_clip(project_id, clip_id, split_ms, keep)

    def nudge_timeline_clip(self, project_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.nudge_timeline_clip(project_id, payload)

    def ripple_insert_timeline_clip(self, project_id: int, payload: Dict) -> Optional[Dict]:
        return studio_service.ripple_insert_timeline_clip(project_id, payload)

    def reorder_timeline_clips(self, project_id: int, payload: Dict) -> Dict:
        return studio_service.reorder_timeline_clips(project_id, payload)


editor_timeline_service = EditorTimelineService()
