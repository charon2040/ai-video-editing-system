import os
import subprocess
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        # 默认使用 Edge TTS
        # 指向虚拟环境中的绝对路径，避免找不到环境变量
        self.edge_tts_bin = r"E:\anaconda\envs\funasr-env\Scripts\edge-tts.exe"

    def generate_tts_and_subtitles(self, text: str, output_audio_path: str, output_srt_path: str, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%") -> bool:
        """
        使用 edge-tts 生成音频和字幕文件 (SRT格式)
        """
        try:
            # edge-tts 的 --write-subtitles 输出的其实是 SRT 格式
            cmd = [
                self.edge_tts_bin,
                "-v", voice,
                "--rate", rate,
                "--text", text,
                "--write-media", output_audio_path,
                "--write-subtitles", output_srt_path
            ]
            logger.info(f"Running TTS command: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("TTS generation completed successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"TTS Generation failed: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error(f"TTS executable not found. Ensure '{self.edge_tts_bin}' is in PATH or installed via 'pip install edge-tts'.")
            return False

    def generate_tts_only(self, text: str, output_audio_path: str, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%") -> bool:
        """
        仅生成TTS音频（不生成SRT）
        """
        try:
            cmd = [
                self.edge_tts_bin,
                "-v", voice,
                "--rate", rate,
                "--text", text,
                "--write-media", output_audio_path
            ]
            logger.info(f"Running TTS command: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"TTS Generation failed: {e.stderr}")
            return False
        except FileNotFoundError:
            logger.error(f"TTS executable not found. Ensure '{self.edge_tts_bin}' is in PATH or installed via 'pip install edge-tts'.")
            return False

    def probe_audio_duration_ms(self, audio_path: str) -> int:
        """
        使用 ffprobe 获取音频时长（毫秒）
        """
        if not audio_path or not os.path.exists(audio_path):
            return 0
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ]
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            seconds = float((result.stdout or "0").strip() or 0)
            return max(0, int(round(seconds * 1000)))
        except Exception as exc:
            logger.error("Failed to probe audio duration for %s: %s", audio_path, exc)
            return 0

    def synthesize_segments_with_duration(
        self,
        segments: List[Dict[str, Any]],
        output_dir: str,
        base_name: str,
        voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+20%",
        keep_audio: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        逐段生成配音，获取每段真实音频时长，供第二轮选片使用。
        可选保留测时音频，供后续正式合成时直接复用，避免再次调用 TTS。
        """
        measured_segments: List[Dict[str, Any]] = []
        os.makedirs(output_dir, exist_ok=True)

        for index, seg in enumerate(segments):
            text = str(seg.get("text", "") or seg.get("dubbing", "") or "").strip()
            if not text:
                continue
            segment_index = int(seg.get("segment_index", index) or index)
            temp_audio_path = os.path.join(output_dir, f"{base_name}_tts_probe_{index}.mp3")
            if not self.generate_tts_only(text, temp_audio_path, voice=voice, rate=rate):
                raise RuntimeError(f"TTS generation failed for segment {index}")
            duration_ms = self.probe_audio_duration_ms(temp_audio_path)
            measured_segments.append(
                {
                    **dict(seg),
                    "segment_index": segment_index,
                    "text": text,
                    "dubbing": text,
                    "required_duration_ms": duration_ms,
                    "tts_duration_ms": duration_ms,
                    "tts_probe_audio_path": temp_audio_path if keep_audio else "",
                }
            )
            logger.info(
                "Measured TTS duration for segment %s: %sms, text=%s",
                index,
                duration_ms,
                text[:80],
            )
            if not keep_audio:
                try:
                    os.remove(temp_audio_path)
                except OSError:
                    logger.warning("Failed to remove temp tts probe audio: %s", temp_audio_path)

        return measured_segments

tts_service = TTSService()
