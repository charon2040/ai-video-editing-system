import subprocess
import os
from typing import List, Dict, Any

class VideoService:
    def __init__(self):
        pass

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
        """
        try:
            temp_files = []
            concat_list_path = os.path.join(os.path.dirname(output_video), "concat_list.txt")
            ass_subtitles = []
            
            # 累积当前的时间（用于生成连续的字幕时间轴）
            current_time_ms = 0
            
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for i, seg in enumerate(segments):
                    start_sec = seg["start"] / 1000.0
                    end_sec = seg["end"] / 1000.0
                    duration = end_sec - start_sec
                    duration_ms = int(duration * 1000)
                    
                    temp_output = os.path.join(os.path.dirname(output_video), f"temp_seg_{i}.mp4")
                    temp_audio = os.path.join(os.path.dirname(output_video), f"temp_a_{i}.mp3")

                    dubbing_text = seg.get("dubbing", "").strip()

                    if dubbing_text:
                        if not tts_service_instance.generate_tts_only(dubbing_text, temp_audio, rate="+20%"):
                            return False, []

                        cmd_merge = [
                            "ffmpeg", "-y",
                            "-ss", str(start_sec),
                            "-t", str(duration),
                            "-i", input_video,
                            "-i", temp_audio,
                            "-map", "0:v:0",
                            "-map", "1:a:0",
                            "-c:v", "libx264",
                            "-preset", "veryfast",
                            "-c:a", "aac",
                            "-af", "apad",
                            "-t", str(duration),
                            temp_output
                        ]
                        subprocess.run(cmd_merge, check=True, capture_output=True)

                        ass_subtitles.append({
                            "start": current_time_ms,
                            "end": current_time_ms + duration_ms,
                            "content": dubbing_text,
                            "is_highlight": True
                        })
                    else:
                        cmd_orig = [
                            "ffmpeg", "-y",
                            "-f", "lavfi",
                            "-t", str(duration),
                            "-i", "anullsrc=r=44100:cl=stereo",
                            "-ss", str(start_sec),
                            "-i", input_video,
                            "-map", "1:v:0",
                            "-map", "0:a:0",
                            "-c:v", "libx264",
                            "-preset", "veryfast",
                            "-c:a", "aac",
                            "-shortest",
                            temp_output
                        ]
                        subprocess.run(cmd_orig, check=True, capture_output=True)

                    temp_files.append(temp_output)
                    if os.path.exists(temp_audio):
                        temp_files.append(temp_audio)
                    f.write(f"file '{temp_output}'\n")

                    current_time_ms += duration_ms

            concat_cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_list_path,
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-c:a", "aac",
                output_video
            ]
            subprocess.run(concat_cmd, check=True, capture_output=True)

            os.remove(concat_list_path)
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
