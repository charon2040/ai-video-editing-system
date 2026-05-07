import subprocess
import os
from typing import List, Dict, Any

class VideoService:
    def __init__(self):
        pass

    def extract_audio_track(self, input_media: str, output_audio: str) -> bool:
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", input_media,
                "-vn",
                "-acodec", "mp3",
                output_audio
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg Extract Audio Error: {e.stderr.decode('utf-8') if e.stderr else e}")
            return False

    def cut_and_concat_video(self, input_video: str, output_video: str, segments: List[Dict[str, Any]]) -> bool:
        """
        根据 LLM 返回的时间段，使用 FFmpeg 剪辑拼接视频
        segments: [{"start": 1000, "end": 5000}, ...] (单位：毫秒)
        """
        try:
            # 创建中间片段列表
            temp_files = []
            concat_list_path = os.path.join(os.path.dirname(output_video), "concat_list.txt")
            
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(segments):
                    start_sec = seg["start"] / 1000.0
                    end_sec = seg["end"] / 1000.0
                    duration = end_sec - start_sec
                    
                    temp_output = os.path.join(os.path.dirname(output_video), f"temp_seg_{i}.mp4")
                    temp_files.append(temp_output)
                    
                    # 裁剪片段
                    cmd = [
                        "ffmpeg", "-ss", str(start_sec), "-i", input_video,
                        "-t", str(duration), "-c", "copy", "-y", temp_output
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                    
                    f.write(f"file '{temp_output}'\n")

            # 拼接片段
            concat_cmd = [
                "ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_list_path,
                "-c", "copy", "-y", output_video
            ]
            subprocess.run(concat_cmd, check=True, capture_output=True)
            
            # 清理中间文件
            os.remove(concat_list_path)
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg Error: {e.stderr.decode('utf-8') if e.stderr else e}")
            return False

    def replace_audio_and_add_subtitles(self, input_video: str, new_audio: str, subtitle_file: str, output_video: str) -> bool:
        """
        将视频原声替换为 new_audio，并将 subtitle_file 压制进视频
        """
        try:
            # ffmpeg -i video.mp4 -i audio.mp3 -vf "subtitles=sub.srt" -c:v libx264 -c:a aac -map 0:v:0 -map 1:a:0 -shortest output.mp4
            # 因为字幕路径在 windows 下可能有冒号（如 C:\），ffmpeg 滤镜需要转义，为简单起见，我们改变当前工作目录或使用相对路径
            
            # 为了安全处理路径，使用绝对路径替换反斜杠，并转义冒号
            safe_sub_path = subtitle_file.replace('\\', '/')
            safe_sub_path = safe_sub_path.replace(':', '\\:')
            
            cmd = [
                "ffmpeg",
                "-i", input_video,
                "-i", new_audio,
                "-vf", f"subtitles='{safe_sub_path}'",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest", # 取最短，防止黑屏或静音
                "-y",
                output_video
            ]
            
            print(f"Running ffmpeg dubbing: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg Dubbing Error: {e.stderr.decode('utf-8') if e.stderr else e}")
            return False

    def cut_and_concat_video_with_redub(self, input_video: str, output_video: str, segments: List[Dict[str, Any]], tts_service_instance):
        """
        根据 LLM 返回的时间段剪辑视频，并将对应的 dubbing 转换为音频替换原声。
        红配音模式下不保留原视频原音，避免解说风格割裂。
        如果极少数片段缺少 dubbing，则生成静音轨，保持整条成片音频风格统一。
        同时生成一个包含所有 dubbing 的合并 ASS 字幕文件供后续压制。
        直接使用单次 FFmpeg concat filter 输出整片，避免逐段先编码成 mp4 再二次合并。
        """
        try:
            temp_files = []
            ass_subtitles = []
            cmd = ["ffmpeg", "-y"]
            filter_parts = []
            concat_streams = []
            current_time_ms = 0

            for i, seg in enumerate(segments):
                start_sec = seg["start"] / 1000.0
                end_sec = seg["end"] / 1000.0
                duration = max(end_sec - start_sec, 0.001)
                duration_ms = int(round(duration * 1000))
                tts_duration_ms = int(seg.get("tts_duration_ms", seg.get("required_duration_ms", duration_ms)) or duration_ms)
                dubbing_text = str(seg.get("dubbing", "") or "").strip()

                video_input_index = i * 2
                audio_input_index = i * 2 + 1

                cmd.extend(["-ss", str(start_sec), "-t", str(duration), "-i", input_video])

                if dubbing_text:
                    measured_audio = str(seg.get("tts_probe_audio_path", "") or "").strip()
                    temp_audio = os.path.join(os.path.dirname(output_video), f"temp_a_{i}.mp3")
                    audio_input = measured_audio if measured_audio and os.path.exists(measured_audio) else temp_audio
                    if audio_input == temp_audio:
                        if not tts_service_instance.generate_tts_only(dubbing_text, temp_audio, rate="+20%"):
                            return False, []
                    if os.path.exists(audio_input):
                        temp_files.append(audio_input)
                    cmd.extend(["-i", audio_input])
                    ass_subtitles.append({
                        "start": current_time_ms,
                        "end": current_time_ms + min(duration_ms, max(tts_duration_ms, 1)),
                        "content": dubbing_text,
                        "is_highlight": True
                    })
                else:
                    cmd.extend(["-f", "lavfi", "-t", str(duration), "-i", "anullsrc=r=44100:cl=stereo"])

                filter_parts.append(
                    f"[{video_input_index}:v]setpts=PTS-STARTPTS[v{i}]"
                )
                filter_parts.append(
                    f"[{audio_input_index}:a]aresample=44100,asetpts=PTS-STARTPTS,apad,atrim=duration={duration:.3f}[a{i}]"
                )
                concat_streams.append(f"[v{i}][a{i}]")
                current_time_ms += duration_ms

            if not concat_streams:
                return False, []

            filter_parts.append(
                "".join(concat_streams) + f"concat=n={len(segments)}:v=1:a=1[vout][aout]"
            )

            cmd.extend([
                "-filter_complex", ";".join(filter_parts),
                "-map", "[vout]",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-c:a", "aac",
                output_video
            ])
            subprocess.run(cmd, check=True, capture_output=True)

            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass

            return True, ass_subtitles
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg Error in redubbing: {e.stderr.decode('utf-8') if e.stderr else e}")
            return False, []

video_service = VideoService()
