import os
import subprocess
import tempfile
from typing import Any, Dict, List, Tuple

from app.core.config import settings
from app.services.editor_logic_registry import normalize_transition_type

class AdvancedRenderService:
    def __init__(self):
        pass

    def _escape_filter_path(self, file_path: str) -> str:
        return file_path.replace("\\", "/").replace(":", "\\:")

    def _seconds(self, value_ms: int) -> float:
        return max(0.0, float(value_ms or 0) / 1000.0)

    def _clamp(self, value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, value))

    def _parse_resolution(self, resolution: str) -> Tuple[int, int]:
        try:
            width_str, height_str = str(resolution or "1920x1080").lower().split("x", 1)
            return max(16, int(width_str)), max(16, int(height_str))
        except Exception:
            return 1920, 1080

    def _find_existing_path(self, raw_path: str) -> str:
        if not raw_path:
            return ""
        normalized = raw_path.strip()
        if normalized.startswith("/download/"):
            normalized = os.path.join(settings.OUTPUT_FOLDER, os.path.basename(normalized))
        if os.path.isabs(normalized) and os.path.exists(normalized):
            return normalized
        basename = os.path.basename(normalized)
        candidates = [
            normalized,
            os.path.join(settings.UPLOAD_FOLDER, basename),
            os.path.join(settings.OUTPUT_FOLDER, basename),
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return ""

    def _is_image_file(self, file_path: str) -> bool:
        return os.path.splitext(file_path)[1].lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

    def _has_audio_stream(self, file_path: str) -> bool:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a",
                    "-show_entries",
                    "stream=index",
                    "-of",
                    "csv=p=0",
                    file_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def _get_media_duration_seconds(self, file_path: str) -> float:
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    file_path,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            return max(0.1, float(result.stdout.strip()))
        except Exception:
            return 60.0

    def _resolve_clip_source_path(self, clip: Dict[str, Any]) -> str:
        metadata = clip.get("metadata") or {}
        source_path = metadata.get("source_path") or clip.get("resolved_source_path") or ""
        return self._find_existing_path(source_path)

    def _normalize_audio_role(self, role: str) -> str:
        value = str(role or "bgm").strip().lower()
        if value in {"voice", "voiceover", "narration", "dub", "dialog"}:
            return "voiceover"
        if value in {"sfx", "fx", "effect"}:
            return "sfx"
        return "bgm"

    def _build_audio_track_filter(
        self,
        input_index: int,
        clip: Dict[str, Any],
        output_label: str,
        render_config: Dict[str, Any],
    ) -> str:
        start_ms = int(clip.get("start_ms", 0) or 0)
        end_ms = int(clip.get("end_ms", 0) or 0)
        duration = max(0.1, self._seconds(end_ms - start_ms))
        metadata = clip.get("metadata") or {}
        volume = self._clamp(float(metadata.get("volume", 1.0) or 1.0), 0.0, 4.0)
        fade_in_sec = self._seconds(int(metadata.get("fade_in_ms", 0) or 0))
        fade_out_sec = self._seconds(int(metadata.get("fade_out_ms", 0) or 0))
        delay = max(0, start_ms)

        filters = [
            f"[{input_index}:a]atrim=duration={duration:.3f}",
            "asetpts=PTS-STARTPTS",
            f"volume={volume:.3f}",
        ]

        if render_config.get("audio_enhance", True):
            if fade_in_sec > 0:
                filters.append(f"afade=t=in:st=0:d={min(fade_in_sec, duration):.3f}")
            if fade_out_sec > 0:
                fade_out_start = max(0.0, duration - fade_out_sec)
                filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={min(fade_out_sec, duration):.3f}")

        filters.append(f"adelay={delay}|{delay}")
        return f"{','.join(filters)}[{output_label}]"

    def _build_ai_effect_filters(
        self,
        start_sec: float,
        end_sec: float,
        effects: Dict[str, Any],
        metadata: Dict[str, Any],
        transform: Dict[str, Any],
    ) -> List[str]:
        vf_filters: List[str] = []
        if end_sec <= start_sec:
            return vf_filters
        enable_expr = f"between(t,{start_sec:.3f},{end_sec:.3f})"
        clip_duration = max(0.1, end_sec - start_sec)
        motion_in = str(metadata.get("motion_in", "none") or "none").strip().lower()
        motion_out = str(metadata.get("motion_out", "none") or "none").strip().lower()
        motion_in_duration = self._clamp(min(0.45, clip_duration * 0.5), 0.08, clip_duration)
        motion_out_duration = self._clamp(min(0.45, clip_duration * 0.5), 0.08, clip_duration)

        if effects.get("highlight") or effects.get("color_boost"):
            vf_filters.append(
                f"eq=contrast=1.08:brightness=0.03:saturation=1.30:enable='{enable_expr}'"
            )
        if effects.get("blur"):
            blur_strength = int(effects.get("blur_strength", 6) or 6)
            blur_strength = max(1, min(24, blur_strength))
            vf_filters.append(f"boxblur={blur_strength}:enable='{enable_expr}'")
        if effects.get("grayscale"):
            vf_filters.append(f"hue=s=0:enable='{enable_expr}'")
        if effects.get("flip_h"):
            vf_filters.append(f"hflip=enable='{enable_expr}'")
        if effects.get("fade_in"):
            vf_filters.append(
                f"fade=t=in:st={start_sec:.3f}:d=0.35:enable='between(t,{start_sec:.3f},{min(end_sec, start_sec + 0.4):.3f})'"
            )
        if effects.get("fade_out"):
            fade_start = max(start_sec, end_sec - 0.35)
            vf_filters.append(
                f"fade=t=out:st={fade_start:.3f}:d=0.35:enable='between(t,{fade_start:.3f},{end_sec:.3f})'"
            )
        if motion_in in {"fade", "slide_left", "slide_right", "slide_top", "slide_bottom", "zoom_in", "rotate_in"}:
            vf_filters.append(
                f"fade=t=in:st={start_sec:.3f}:d={motion_in_duration:.3f}:enable='between(t,{start_sec:.3f},{min(end_sec, start_sec + motion_in_duration):.3f})'"
            )
        if motion_out in {"fade", "slide_left", "slide_right", "slide_top", "slide_bottom", "zoom_in", "rotate_in"}:
            motion_out_start = max(start_sec, end_sec - motion_out_duration)
            vf_filters.append(
                f"fade=t=out:st={motion_out_start:.3f}:d={motion_out_duration:.3f}:enable='between(t,{motion_out_start:.3f},{end_sec:.3f})'"
            )
        if motion_in in {"rotate", "rotate_in"}:
            vf_filters.append(
                f"rotate='0.22*exp(-6*(t-{start_sec:.3f}))':c=black@0:enable='between(t,{start_sec:.3f},{min(end_sec, start_sec + motion_in_duration):.3f})'"
            )
        if motion_out in {"rotate", "rotate_in"}:
            motion_out_start = max(start_sec, end_sec - motion_out_duration)
            vf_filters.append(
                f"rotate='0.22*exp(-6*({end_sec:.3f}-t))':c=black@0:enable='between(t,{motion_out_start:.3f},{end_sec:.3f})'"
            )

        rotate_deg = float(transform.get("rotate", 0) or 0)
        if abs(rotate_deg) >= 0.1:
            rotate_rad = rotate_deg * 3.1415926535 / 180.0
            vf_filters.append(
                f"rotate={rotate_rad:.6f}:c=black@0:enable='{enable_expr}'"
            )

        # WebCut 风格滤镜列表（挂在 metadata.filters）
        for item in metadata.get("filters", []) if isinstance(metadata.get("filters", []), list) else []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or item.get("name") or "").strip().lower()
            params = item.get("params") or {}
            if key in {"blur", "gaussian_blur", "boxblur"}:
                sigma = max(1, min(24, int(params.get("value", params.get("radius", 6)) or 6)))
                vf_filters.append(f"boxblur={sigma}:enable='{enable_expr}'")
            elif key in {"brightness", "bright"}:
                value = self._clamp(float(params.get("value", 0.05) or 0.05), -1.0, 1.0)
                vf_filters.append(f"eq=brightness={value:.3f}:enable='{enable_expr}'")
            elif key in {"contrast"}:
                value = self._clamp(float(params.get("value", 1.1) or 1.1), 0.1, 3.0)
                vf_filters.append(f"eq=contrast={value:.3f}:enable='{enable_expr}'")
            elif key in {"saturation", "saturate"}:
                value = self._clamp(float(params.get("value", 1.2) or 1.2), 0.0, 3.0)
                vf_filters.append(f"eq=saturation={value:.3f}:enable='{enable_expr}'")
            elif key in {"grayscale", "blackwhite"}:
                vf_filters.append(f"hue=s=0:enable='{enable_expr}'")
            elif key in {"sepia"}:
                vf_filters.append(f"colorchannelmixer=.393:.769:.189:.349:.686:.168:.272:.534:.131:enable='{enable_expr}'")
            elif key in {"invert"}:
                vf_filters.append(f"negate=enable='{enable_expr}'")
            elif key in {"flip_h", "flip-h", "horizontal_flip", "hflip"}:
                vf_filters.append(f"hflip=enable='{enable_expr}'")
        return vf_filters

    def _build_timeline_transition_filters(self, clips: List[Dict[str, Any]]) -> List[str]:
        filters: List[str] = []
        for clip in clips:
            transition = clip.get("transition") or {}
            start_sec = self._seconds(clip.get("start_ms", 0))
            end_sec = self._seconds(clip.get("end_ms", 0))
            if end_sec <= start_sec:
                continue

            transition_out = transition.get("out") if isinstance(transition.get("out"), dict) else None
            if transition_out:
                t_type = normalize_transition_type(str(transition_out.get("type") or "fade"))
                if t_type in {"fade", "dissolve", "dip_black"}:
                    duration = self._seconds(int(transition_out.get("duration_ms", 400) or 400))
                    duration = self._clamp(duration, 0.08, max(0.08, end_sec - start_sec))
                    fade_start = max(start_sec, end_sec - duration)
                    filters.append(
                        f"fade=t=out:st={fade_start:.3f}:d={duration:.3f}:enable='between(t,{fade_start:.3f},{end_sec:.3f})'"
                    )
                    if t_type == "dip_black":
                        filters.append(
                            f"eq=brightness=-0.18:enable='between(t,{fade_start:.3f},{end_sec:.3f})'"
                        )

            transition_in = transition.get("in") if isinstance(transition.get("in"), dict) else None
            if transition_in:
                t_type = normalize_transition_type(str(transition_in.get("type") or "fade"))
                if t_type in {"fade", "dissolve", "dip_black"}:
                    duration = self._seconds(int(transition_in.get("duration_ms", 400) or 400))
                    duration = self._clamp(duration, 0.08, max(0.08, end_sec - start_sec))
                    fade_end = min(end_sec, start_sec + duration)
                    filters.append(
                        f"fade=t=in:st={start_sec:.3f}:d={duration:.3f}:enable='between(t,{start_sec:.3f},{fade_end:.3f})'"
                    )
                    if t_type == "dip_black":
                        filters.append(
                            f"eq=brightness=-0.18:enable='between(t,{start_sec:.3f},{fade_end:.3f})'"
                        )
        return filters

    def _is_track_effectively_hidden_or_muted(
        self,
        timeline: Dict[str, Any],
        track_type: str,
        track_index: int,
        for_audio: bool = False,
    ) -> bool:
        tracks = timeline.get("tracks", []) if isinstance(timeline, dict) else []
        for track in tracks:
            if (
                str(track.get("track_type", "")) == str(track_type)
                and int(track.get("track_index", 0) or 0) == int(track_index or 0)
            ):
                if not bool(track.get("is_visible", True)):
                    return True
                if for_audio and bool(track.get("is_muted", False)):
                    return True
                return False
        return False

    def _effective_clips(self, timeline: Dict[str, Any], track_types: set, for_audio: bool = False) -> List[Dict[str, Any]]:
        clips = timeline.get("clips", []) if isinstance(timeline, dict) else []
        result: List[Dict[str, Any]] = []
        for clip in clips:
            track_type = str(clip.get("track_type", ""))
            if track_type not in track_types:
                continue
            if self._is_track_effectively_hidden_or_muted(
                timeline,
                track_type,
                int(clip.get("track_index", 0) or 0),
                for_audio=for_audio,
            ):
                continue
            result.append(clip)
        return result

    def build_timeline_filter_chain(self, timeline: Dict[str, Any], ass_file_path: str = "") -> str:
        vf_filters: List[str] = []
        video_clips = self._effective_clips(timeline, {"video"})

        for clip in video_clips:
            start_sec = self._seconds(clip.get("start_ms", 0))
            end_sec = self._seconds(clip.get("end_ms", 0))
            if end_sec <= start_sec:
                continue

            effects = clip.get("effects") or {}
            metadata = clip.get("metadata") or {}
            transform = clip.get("transform") or {}
            vf_filters.extend(self._build_ai_effect_filters(start_sec, end_sec, effects, metadata, transform))

        vf_filters.extend(self._build_timeline_transition_filters(video_clips))

        if ass_file_path:
            vf_filters.append(f"ass='{self._escape_filter_path(ass_file_path)}'")

        return ",".join(vf_filters)

    def _collect_subtitle_segments(self, timeline: Dict[str, Any]) -> List[Dict[str, Any]]:
        subtitle_clips = [
            clip for clip in self._effective_clips(timeline, {"subtitle"})
            if clip.get("track_type") == "subtitle" and str(clip.get("content", "")).strip()
        ]
        if not subtitle_clips:
            subtitle_clips = [
                clip for clip in self._effective_clips(timeline, {"video"})
                if clip.get("track_type") == "video"
                and str(clip.get("dubbing") or clip.get("content") or "").strip()
            ]

        subtitle_clips.sort(key=lambda clip: (clip.get("start_ms", 0), clip.get("sort_order", 0)))
        return [
            {
                "start": clip.get("start_ms", 0),
                "end": clip.get("end_ms", 0),
                "text": str(clip.get("content") or clip.get("dubbing") or "").strip(),
                "is_highlight": bool((clip.get("effects") or {}).get("highlight")),
                "pos_x": float((clip.get("transform") or {}).get("x", 0.5) or 0.5),
                "pos_y": float((clip.get("transform") or {}).get("y", 0.86) or 0.86),
                "scale": float((clip.get("transform") or {}).get("scale", 1.0) or 1.0),
                "style": ((clip.get("metadata") or {}).get("subtitle_style") or {}),
                "highlights": ((clip.get("metadata") or {}).get("subtitle_highlights") or []),
            }
            for clip in subtitle_clips
            if str(clip.get("content") or clip.get("dubbing") or "").strip()
        ]

    def _write_filter_script(self, filters: List[str]) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".ffscript", delete=False, encoding="utf-8") as handle:
            handle.write(";\n".join(filters))
            return handle.name

    def _build_overlay_filters(
        self,
        current_video_label: str,
        overlay_clips: List[Dict[str, Any]],
        base_width: int,
    ) -> Tuple[List[str], str, List[Dict[str, Any]]]:
        filters: List[str] = []
        overlay_inputs: List[Dict[str, Any]] = []
        video_label = current_video_label

        for index, clip in enumerate(overlay_clips):
            source_path = self._resolve_clip_source_path(clip)
            if not source_path:
                continue

            input_index = len(overlay_inputs) + 1
            transform = clip.get("transform") or {}
            effects = clip.get("effects") or {}
            metadata = clip.get("metadata") or {}
            start_sec = self._seconds(clip.get("start_ms", 0))
            end_sec = self._seconds(clip.get("end_ms", 0))
            duration_sec = max(0.1, end_sec - start_sec)
            scale_ratio = self._clamp(float(transform.get("scale", 0.3) or 0.3), 0.05, 3.0)
            opacity = self._clamp(float(transform.get("opacity", 1.0) or 1.0), 0.05, 1.0)
            pos_x = self._clamp(float(transform.get("x", 0.1) or 0.1), 0.0, 1.0)
            pos_y = self._clamp(float(transform.get("y", 0.1) or 0.1), 0.0, 1.0)
            scaled_width = max(24, int(base_width * scale_ratio))

            overlay_inputs.append(
                {
                    "input_index": input_index,
                    "source_path": source_path,
                    "is_image": self._is_image_file(source_path),
                }
            )

            overlay_label = f"ov{index}"
            next_video_label = f"vov{index}"
            overlay_filters = [f"[{input_index}:v]setpts=PTS-STARTPTS", f"scale={scaled_width}:-1", "format=rgba"]
            if effects.get("flip_h"):
                overlay_filters.append("hflip")
            rotate_deg = float(transform.get("rotate", 0) or 0)
            if abs(rotate_deg) >= 0.1:
                rotate_rad = rotate_deg * 3.1415926535 / 180.0
                overlay_filters.append(f"rotate={rotate_rad:.6f}:c=black@0")

            motion_in = str(metadata.get("motion_in", "none") or "none").strip().lower()
            motion_out = str(metadata.get("motion_out", "none") or "none").strip().lower()
            motion_in_duration = self._clamp(min(0.45, duration_sec * 0.5), 0.08, duration_sec)
            motion_out_duration = self._clamp(min(0.45, duration_sec * 0.5), 0.08, duration_sec)
            if motion_in in {"fade", "slide_left", "slide_right", "slide_top", "slide_bottom", "zoom_in", "rotate_in"}:
                overlay_filters.append(f"fade=t=in:st=0:d={motion_in_duration:.3f}:alpha=1")
            if motion_out in {"fade", "slide_left", "slide_right", "slide_top", "slide_bottom", "zoom_in", "rotate_in"}:
                out_start = max(0.0, duration_sec - motion_out_duration)
                overlay_filters.append(f"fade=t=out:st={out_start:.3f}:d={motion_out_duration:.3f}:alpha=1")
            if motion_in in {"rotate", "rotate_in"}:
                overlay_filters.append("rotate='0.24*exp(-6*t)':c=black@0")
            if motion_out in {"rotate", "rotate_in"}:
                overlay_filters.append(f"rotate='0.24*exp(-6*({duration_sec:.3f}-t))':c=black@0")

            if opacity < 0.999:
                overlay_filters.append(f"colorchannelmixer=aa={opacity:.3f}")
            overlay_filters.append(f"trim=duration={duration_sec:.3f}")
            filters.append(f"{','.join(overlay_filters)}[{overlay_label}]")
            filters.append(
                f"{video_label}[{overlay_label}]overlay="
                f"x=main_w*{pos_x:.4f}:y=main_h*{pos_y:.4f}:"
                f"enable='between(t,{start_sec:.3f},{end_sec:.3f})'[{next_video_label}]"
            )
            video_label = f"[{next_video_label}]"

        return filters, video_label, overlay_inputs

    def _build_audio_filters(
        self,
        audio_clips: List[Dict[str, Any]],
        start_input_index: int,
        source_video_path: str,
        render_config: Dict[str, Any],
    ) -> Tuple[List[str], List[Dict[str, Any]], bool, bool]:
        filters: List[str] = []
        audio_inputs: List[Dict[str, Any]] = []
        input_index = start_input_index

        for clip in audio_clips:
            source_path = self._resolve_clip_source_path(clip)
            if not source_path:
                continue
            audio_inputs.append({"input_index": input_index, "source_path": source_path})
            input_index += 1

        has_base_audio = self._has_audio_stream(source_video_path)
        duration_sec = self._get_media_duration_seconds(source_video_path)
        base_audio_volume = self._clamp(float(render_config.get("source_audio_volume", 1.0) or 1.0), 0.0, 4.0)
        ducking_enabled = bool(render_config.get("enable_ducking", True))
        duck_source_audio = bool(render_config.get("duck_source_audio", False))
        ducking_strength = self._clamp(float(render_config.get("ducking_strength", 0.35) or 0.35), 0.05, 1.0)
        threshold = self._clamp(float(render_config.get("ducking_threshold", 0.03) or 0.03), 0.001, 1.0)
        audio_enhance = bool(render_config.get("audio_enhance", True))

        if not audio_inputs:
            if not has_base_audio:
                return [], [], False, False
            if abs(base_audio_volume - 1.0) < 0.001 and not audio_enhance:
                return [], [], True, False

            filters.append(f"[0:a]volume={base_audio_volume:.3f}[a0]")
            final_mix = "[a0]"
            if audio_enhance:
                final_mix += "dynaudnorm=f=150:g=9,"
            final_mix += f"alimiter=limit=0.95,atrim=duration={duration_sec:.3f}[aout]"
            filters.append(final_mix)
            return filters, [], True, True

        master_inputs: List[str] = []
        bgm_inputs: List[str] = []
        voice_inputs: List[str] = []
        sfx_inputs: List[str] = []

        if has_base_audio:
            filters.append(f"[0:a]volume={base_audio_volume:.3f}[a0]")
            if duck_source_audio:
                bgm_inputs.append("[a0]")
            else:
                master_inputs.append("[a0]")
        else:
            filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration_sec:.3f}[asilent]")
            master_inputs.append("[asilent]")

        for index, item in enumerate(audio_inputs, start=1):
            clip = audio_clips[index - 1]
            output_label = f"a{index}"
            filters.append(
                self._build_audio_track_filter(item["input_index"], clip, output_label, render_config)
            )
            role = self._normalize_audio_role((clip.get("metadata") or {}).get("audio_role", "bgm"))
            label_ref = f"[{output_label}]"
            if role == "voiceover":
                voice_inputs.append(label_ref)
            elif role == "sfx":
                sfx_inputs.append(label_ref)
            else:
                bgm_inputs.append(label_ref)

        if bgm_inputs:
            filters.append(
                f"{''.join(bgm_inputs)}amix=inputs={len(bgm_inputs)}:duration=longest:normalize=0[abgm]"
            )
            bgm_label = "[abgm]"
        else:
            bgm_label = ""

        if voice_inputs:
            filters.append(
                f"{''.join(voice_inputs)}amix=inputs={len(voice_inputs)}:duration=longest:normalize=0[avoice]"
            )
            voice_label = "[avoice]"
        else:
            voice_label = ""

        if sfx_inputs:
            filters.append(
                f"{''.join(sfx_inputs)}amix=inputs={len(sfx_inputs)}:duration=longest:normalize=0[asfx]"
            )
            sfx_label = "[asfx]"
        else:
            sfx_label = ""

        if bgm_label and voice_label and ducking_enabled:
            ratio = max(2.0, round(4 + (1 - ducking_strength) * 10, 2))
            filters.append(
                f"{bgm_label}{voice_label}sidechaincompress="
                f"threshold={threshold:.3f}:ratio={ratio:.2f}:attack=20:release=350[abgmduck]"
            )
            master_inputs.append("[abgmduck]")
            master_inputs.append(voice_label)
        else:
            if bgm_label:
                master_inputs.append(bgm_label)
            if voice_label:
                master_inputs.append(voice_label)

        if sfx_label:
            master_inputs.append(sfx_label)

        if not master_inputs:
            filters.append(f"anullsrc=r=44100:cl=stereo,atrim=duration={duration_sec:.3f}[asilentmix]")
            master_inputs.append("[asilentmix]")

        final_mix = (
            f"{''.join(master_inputs)}amix=inputs={len(master_inputs)}:duration=longest:normalize=0,"
        )
        if audio_enhance:
            final_mix += "dynaudnorm=f=150:g=9,"
        final_mix += f"alimiter=limit=0.95,atrim=duration={duration_sec:.3f}[aout]"
        filters.append(final_mix)
        return filters, audio_inputs, has_base_audio, True
        
    def _split_text(self, text: str, max_chars: int = 15) -> str:
        """
        长字幕分行处理
        """
        if len(text) <= max_chars:
            return text
        
        words = text.replace('，', ' ').replace('。', ' ').replace(',', ' ').replace('.', ' ').split()
        if len(words) > 1:
            # 如果有空格/标点分割的词，按词截断
            lines = []
            current_line = ""
            for word in words:
                if len(current_line) + len(word) > max_chars:
                    if current_line:
                        lines.append(current_line.strip())
                    current_line = word
                else:
                    current_line += " " + word if current_line else word
            if current_line:
                lines.append(current_line.strip())
            return "\\N".join(lines)
        else:
            # 如果是纯中文字符串没有空格，直接按字数硬截断
            return text[:max_chars] + "\\N" + text[max_chars:]

    def _hex_to_ass_color(self, value: str, fallback: str = "&H00FFFFFF") -> str:
        text = str(value or "").strip()
        if not text:
            return fallback
        if text.startswith("&H"):
            return text
        if text.startswith("#"):
            text = text[1:]
        if len(text) == 3:
            text = "".join([ch * 2 for ch in text])
        if len(text) != 6:
            return fallback
        try:
            r = int(text[0:2], 16)
            g = int(text[2:4], 16)
            b = int(text[4:6], 16)
            return f"&H{b:02X}{g:02X}{r:02X}&"
        except Exception:
            return fallback

    def _apply_ass_highlights(self, text: str, highlights: List[Dict[str, Any]]) -> str:
        if not text or not highlights:
            return text
        ranges = []
        length = len(text)
        for item in highlights:
            if not isinstance(item, dict):
                continue
            try:
                start = int(item.get("start", 0))
                end = int(item.get("end", 0))
            except Exception:
                continue
            if end <= start:
                continue
            start = max(0, min(length, start))
            end = max(0, min(length, end))
            if end <= start:
                continue
            css = item.get("css") or {}
            color = item.get("color") or (css.get("color") if isinstance(css, dict) else "")
            ass_color = self._hex_to_ass_color(str(color or ""), "&H00FFFF&")
            ranges.append((start, end, ass_color))
        if not ranges:
            return text
        ranges.sort(key=lambda x: (x[0], x[1]))
        merged = []
        for start, end, color in ranges:
            if not merged:
                merged.append([start, end, color])
                continue
            last = merged[-1]
            if start <= last[1]:
                last[1] = max(last[1], end)
                continue
            merged.append([start, end, color])

        pieces = []
        cursor = 0
        for start, end, color in merged:
            if cursor < start:
                pieces.append(text[cursor:start])
            pieces.append(r"{\c" + color + r"}" + text[start:end] + r"{\c}")
            cursor = end
        if cursor < length:
            pieces.append(text[cursor:])
        return "".join(pieces)

    def generate_ass_subtitle(self, subtitles: List[Dict[str, Any]], output_path: str, style_config: Dict[str, Any] = None):
        """
        根据 LLM 的决策，生成带特效的 ASS 字幕文件。
        ASS 格式支持复杂的颜色、字体大小、甚至动画特效。
        """
        # 默认样式
        font_size = style_config.get("font_size", 24) if style_config else 24
        primary_color = style_config.get("primary_color", "&H00FFFFFF") if style_config else "&H00FFFFFF" # BGR 格式
        
        ass_header = f"""[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},{primary_color},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        events = []
        for seg in subtitles:
            # 将毫秒转为 ASS 时间格式: H:MM:SS.cs
            start_s = seg["start"] / 1000.0
            end_s = seg["end"] / 1000.0
            
            def format_ass_time(seconds):
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                s = int(seconds % 60)
                cs = int((seconds - int(seconds)) * 100)
                return f"{h}:{m:02d}:{s:02d}.{cs:02d}"
                
            start_time = format_ass_time(start_s)
            end_time = format_ass_time(end_s)
            text = seg.get("text", "")
            style = seg.get("style") or {}
            highlights = seg.get("highlights") or []
            
            # 动态调整字体大小避免溢出
            style_prefix = ""
            pos_x = seg.get("pos_x", None)
            pos_y = seg.get("pos_y", None)
            scale = float(seg.get("scale", 1.0) or 1.0)
            if pos_x is not None and pos_y is not None:
                try:
                    px = max(0.0, min(1.0, float(pos_x)))
                    py = max(0.0, min(1.0, float(pos_y)))
                    x = int(px * 1920)
                    y = int(py * 1080)
                    style_prefix += r"{\pos(" + str(x) + "," + str(y) + r")}"
                except Exception:
                    pass
            if abs(scale - 1.0) > 0.001:
                scaled_font = max(12, int(font_size * max(0.3, min(3.0, scale))))
                style_prefix += r"{\fs" + str(scaled_font) + r"}"
            if style.get("bold"):
                style_prefix += r"{\b1}"
            if style.get("italic"):
                style_prefix += r"{\i1}"
            if style.get("underline"):
                style_prefix += r"{\u1}"
            text_color = str(style.get("color") or "").strip()
            ass_text_color = self._hex_to_ass_color(text_color, "")
            if ass_text_color:
                style_prefix += r"{\c" + ass_text_color + r"}"
            outline_color = str(style.get("outline_color") or "").strip()
            ass_outline_color = self._hex_to_ass_color(outline_color, "")
            if ass_outline_color:
                style_prefix += r"{\3c" + ass_outline_color + r"}"
            if len(text) > 30:
                style_prefix += r"{\fs" + str(int(font_size * 0.8)) + r"}"
                
            # 高亮片段优先；没有高亮时做自动分行
            if isinstance(highlights, list) and highlights:
                text = self._apply_ass_highlights(text, highlights)
            else:
                text = self._split_text(text, max_chars=18)
            
            # 高亮特效
            if seg.get("is_highlight"):
                # 放大 + 变色 + 边框加粗
                style_prefix += r"{\fs" + str(int(font_size * 1.2)) + r"\c&H00FFFF&\3c&HFFFFFF&\bord4}"
                effect_text = f"{style_prefix}{text}"
            else:
                effect_text = f"{style_prefix}{text}"
                
            events.append(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{effect_text}")
            
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ass_header + "\n".join(events))
            
        return output_path

    def apply_advanced_effects(self, input_video: str, output_video: str, render_commands: Dict[str, Any]) -> bool:
        """
        基于 LLM 决策出的复杂特效参数（蒙版、滤镜），调用 FFmpeg 进行高级重渲染。
        render_commands: 包含滤镜图（Filter Graph）参数或 ASS 路径。
        """
        try:
            # 这是一个示例 Filter Graph，实际可由大模型生成
            # 比如应用高斯模糊蒙版，或者烧录刚刚生成的 ASS 字幕
            ass_file = render_commands.get("ass_file_path")
            
            # 注意：在 Windows 环境下 FFmpeg 烧录字幕需要处理路径转义
            ass_path_escaped = ass_file.replace("\\", "/").replace(":", "\\:") if ass_file else ""
            
            vf_filters = []
            if ass_path_escaped:
                vf_filters.append(f"ass='{ass_path_escaped}'")
                
            if render_commands.get("apply_blur"):
                # 在特定时间段应用模糊
                blur_start = render_commands["blur_start"]
                blur_end = render_commands["blur_end"]
                vf_filters.append(f"boxblur=10:enable='between(t,{blur_start},{blur_end})'")
                
            filter_graph = ",".join(vf_filters) if vf_filters else "copy"
            
            cmd = [
                "ffmpeg", "-y", "-i", input_video
            ]
            
            if filter_graph != "copy":
                cmd.extend(["-vf", filter_graph, "-c:a", "copy"])
            else:
                cmd.extend(["-c", "copy"])
                
            cmd.append(output_video)
            
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Advanced Render Error: {e.stderr.decode('utf-8') if e.stderr else e}")
            return False

    def render_timeline_export(
        self,
        source_video_path: str,
        output_video_path: str,
        timeline: Dict[str, Any],
        render_config: Dict[str, Any],
    ) -> bool:
        source_video_path = self._find_existing_path(source_video_path) or source_video_path
        resolution = timeline.get("resolution", "1920x1080")
        width, _ = self._parse_resolution(resolution)
        ass_file_path = ""
        filter_script_path = ""

        if render_config.get("burn_subtitles", True):
            subtitles = self._collect_subtitle_segments(timeline)
        else:
            subtitles = []

        if subtitles:
            ass_file_path = os.path.splitext(output_video_path)[0] + ".ass"
            self.generate_ass_subtitle(subtitles, ass_file_path, style_config={"font_size": 30})

        try:
            cmd = ["ffmpeg", "-y", "-i", source_video_path]
            filters: List[str] = []
            current_video_label = "[0:v]"

            if render_config.get("apply_clip_effects", True):
                base_video_chain = self.build_timeline_filter_chain(timeline, "")
                if base_video_chain:
                    filters.append(f"[0:v]{base_video_chain}[vbase]")
                    current_video_label = "[vbase]"

            overlay_clips = self._effective_clips(timeline, {"pip", "sticker"})
            overlay_filters, current_video_label, overlay_inputs = self._build_overlay_filters(
                current_video_label,
                overlay_clips,
                width,
            )
            filters.extend(overlay_filters)
            for item in overlay_inputs:
                if item["is_image"]:
                    cmd.extend(["-loop", "1", "-i", item["source_path"]])
                else:
                    cmd.extend(["-stream_loop", "-1", "-i", item["source_path"]])

            if ass_file_path:
                filters.append(
                    f"{current_video_label}ass='{self._escape_filter_path(ass_file_path)}'[vfinal]"
                )
                current_video_label = "[vfinal]"

            audio_clips = self._effective_clips(timeline, {"audio"}, for_audio=True)
            audio_filters, audio_inputs, has_base_audio, has_audio_output = self._build_audio_filters(
                audio_clips,
                start_input_index=1 + len(overlay_inputs),
                source_video_path=source_video_path,
                render_config=render_config,
            )
            filters.extend(audio_filters)
            for item in audio_inputs:
                cmd.extend(["-stream_loop", "-1", "-i", item["source_path"]])

            if filters:
                filter_script_path = self._write_filter_script(filters)
                quality = str(render_config.get("quality", "standard"))
                crf = "20" if quality == "high" else "24"
                cmd.extend(
                    [
                        "-filter_complex_script",
                        filter_script_path,
                        "-map",
                        current_video_label,
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        crf,
                    ]
                )
                if has_audio_output:
                    cmd.extend(["-map", "[aout]", "-c:a", "aac"])
                elif has_base_audio:
                    cmd.extend(["-map", "0:a?", "-c:a", "copy"])
                else:
                    cmd.append("-an")
            else:
                cmd.extend(["-c", "copy"])

            cmd.append(output_video_path)
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Timeline Export Error: {e.stderr.decode('utf-8') if e.stderr else e}")
            return False
        finally:
            if filter_script_path and os.path.exists(filter_script_path):
                try:
                    os.remove(filter_script_path)
                except OSError:
                    pass


advanced_render_service = AdvancedRenderService()
