import os
from typing import Dict, Optional

from app.services.editor_export_service import editor_export_service
from app.services.editor_project_service import editor_project_service
from app.services.editor_timeline_service import editor_timeline_service


class EditorAIOrchestrator:
    def build_studio_timeline_from_ai_result(self, result: Dict, enable_redub: bool) -> Dict:
        matched_segments = result.get("matched_segments", []) or []
        effects_cfg = result.get("effects", {}) or {}
        default_subtitle_style = result.get("subtitle_style", {}) if isinstance(result.get("subtitle_style", {}), dict) else {}
        video_clips = []
        subtitle_clips = []
        for index, seg in enumerate(matched_segments):
            segment_start = int(seg.get("start", 0) or 0)
            segment_end = int(seg.get("end", 0) or 0)
            subtitle_text = str(seg.get("dubbing", "") or seg.get("content", "") or "").strip()

            video_clips.append(
                {
                    "asset_id": None,
                    "clip_type": "video",
                    "label": f"AI片段 {index + 1}",
                    "track_type": "video",
                    "track_index": 0,
                    "start_ms": segment_start,
                    "end_ms": segment_end,
                    "source_start_ms": int(seg.get("source_start", seg.get("start", 0)) or 0),
                    "source_end_ms": int(seg.get("source_end", seg.get("end", 0)) or 0),
                    "content": seg.get("content", "") or "",
                    "dubbing": seg.get("dubbing", "") or "",
                    "effects": {
                        "highlight": bool(effects_cfg.get("highlight", True)),
                        "blur": bool(effects_cfg.get("blur", False)),
                        "blur_strength": 6,
                        "grayscale": False,
                        "fade_in": index == 0,
                        "fade_out": index == len(matched_segments) - 1,
                    },
                    "transform": {},
                    "transition": {},
                    "metadata": {
                        "ai_generated": True,
                        "source_path": result.get("timeline_source_video_url", "") or result.get("output_video_url", ""),
                    },
                    "sort_order": index,
                }
            )
            if subtitle_text:
                subtitle_style = {
                    "bold": bool(default_subtitle_style.get("bold", False)),
                    "italic": bool(default_subtitle_style.get("italic", False)),
                    "underline": bool(default_subtitle_style.get("underline", False)),
                    "color": str(default_subtitle_style.get("color", "#FFFFFF")),
                    "outline_color": str(default_subtitle_style.get("outline_color", "#000000")),
                }
                subtitle_highlights = seg.get("subtitle_highlights", [])
                if not isinstance(subtitle_highlights, list):
                    subtitle_highlights = []
                subtitle_clips.append(
                    {
                        "asset_id": None,
                        "clip_type": "subtitle",
                        "label": f"字幕 {index + 1}",
                        "track_type": "subtitle",
                        "track_index": 0,
                        "start_ms": segment_start,
                        "end_ms": segment_end,
                        "source_start_ms": 0,
                        "source_end_ms": max(0, segment_end - segment_start),
                        "content": subtitle_text,
                        "dubbing": "",
                        "effects": {"highlight": bool(effects_cfg.get("highlight", True))},
                        "transform": {"x": 0.5, "y": 0.86, "scale": 1.0, "opacity": 1.0},
                        "transition": {},
                        "metadata": {
                            "ai_generated": True,
                            "subtitle_style": subtitle_style,
                            "subtitle_highlights": subtitle_highlights,
                        },
                        "sort_order": index,
                    }
                )

        clips = list(video_clips) + subtitle_clips
        total_duration = max([int(item.get("end_ms", 0) or 0) for item in video_clips], default=0)
        voiceover_url = result.get("voiceover_audio_url", "") or ""
        if enable_redub and voiceover_url and total_duration > 0:
            clips.append(
                {
                    "asset_id": None,
                    "clip_type": "audio",
                    "label": "AI配音主轨",
                    "track_type": "audio",
                    "track_index": 0,
                    "start_ms": 0,
                    "end_ms": total_duration,
                    "source_start_ms": 0,
                    "source_end_ms": total_duration,
                    "content": "AI 自动配音",
                    "dubbing": result.get("script", "") or "",
                    "effects": {},
                    "transform": {},
                    "transition": {},
                    "metadata": {
                        "source_path": voiceover_url,
                        "audio_role": "voiceover",
                        "volume": 1.1,
                        "fade_in_ms": 120,
                        "fade_out_ms": 220,
                    },
                    "sort_order": len(video_clips),
                }
            )

        return {
            "name": "AI 主时间线",
            "resolution": "1920x1080",
            "fps": 30,
            "script": result.get("script", "") or "",
            "status": "draft",
            "source_video_path": result.get("timeline_source_video_url", "") or result.get("output_video_url", ""),
            "source_edl_path": result.get("output_edl_url", "") or "",
            "render_blueprint": {
                "suggestions": result.get("suggestions", []) or [],
                "effects": effects_cfg,
                "redub": enable_redub,
            },
            "clips": clips,
        }

    def finalize_ai_result_to_project(
        self,
        ai_result: Dict,
        is_redub: bool,
        project_id: Optional[int],
        project_name: str,
        create_export_job: bool,
    ) -> Dict:
        if project_id:
            project = editor_project_service.get_project_detail(int(project_id))
            if not project:
                raise ValueError("Project not found")
            target_project_id = int(project_id)
        else:
            created = editor_project_service.create_project(
                {
                    "name": (project_name or "AI自动剪辑项目").strip() or "AI自动剪辑项目",
                    "description": "由 AI 生成并自动写入时间线",
                    "scenario": "sports_digest",
                    "aspect_ratio": "16:9",
                }
            )
            target_project_id = int(created["id"])

        timeline_payload = self.build_studio_timeline_from_ai_result(ai_result, is_redub)
        timeline = editor_timeline_service.upsert_timeline(target_project_id, timeline_payload)

        registered_assets = []
        output_video_url = ai_result.get("output_video_url", "") or ""
        timeline_source_url = ai_result.get("timeline_source_video_url", "") or ""
        voiceover_audio_url = ai_result.get("voiceover_audio_url", "") or ""
        for file_url, display_name, file_type in [
            (output_video_url, "AI成片", "mp4"),
            (timeline_source_url, "时间线源视频", "mp4"),
            (voiceover_audio_url, "AI配音音轨", "mp3"),
        ]:
            if not file_url:
                continue
            asset = editor_project_service.register_existing_asset(
                target_project_id,
                {
                    "name": f"{display_name}-{os.path.basename(file_url)}",
                    "file_type": file_type,
                    "file_path": file_url,
                    "duration_ms": 0,
                    "transcript_status": "ready",
                },
            )
            if asset:
                registered_assets.append(asset)

        export_job = None
        if bool(create_export_job):
            export_job = editor_export_service.create_export_job(
                target_project_id,
                {
                    "timeline_id": timeline.get("id"),
                    "job_type": "online_render",
                    "source_video_path": timeline.get("source_video_url", ""),
                    "render_config": {
                        "quality": "high",
                        "burn_subtitles": True,
                        "apply_clip_effects": True,
                        "audio_enhance": True,
                        "enable_ducking": True,
                    },
                },
            )

        return {
            "status": "success",
            "project_id": target_project_id,
            "timeline_id": timeline.get("id"),
            "export_job_id": export_job.get("id") if export_job else None,
            "export_job": export_job or {},
            "registered_assets": registered_assets,
            "ai_result": ai_result,
        }


editor_ai_orchestrator = EditorAIOrchestrator()
