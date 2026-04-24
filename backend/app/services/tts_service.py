import os
import subprocess
import logging
from typing import Optional

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

tts_service = TTSService()
