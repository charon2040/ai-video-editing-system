from __future__ import annotations

import subprocess
import threading
from typing import Any, Dict, List

from app.core.config import settings


class ASRService:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _detect_device(self) -> str:
        if settings.funasr_device != "auto":
            return settings.funasr_device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def get_model(self):
        with self._lock:
            if self._model is not None:
                return self._model

            from funasr import AutoModel

            self._model = AutoModel(
                model=settings.funasr_model,
                vad_model=settings.funasr_vad_model,
                vad_kwargs={"max_single_segment_time": 60000},
                punc_model=settings.funasr_punc_model,
                device=self._detect_device(),
            )
            return self._model

    def extract_audio_from_video(self, video_path: str, output_audio_path: str) -> bool:
        cmd = [
            settings.ffmpeg_bin,
            "-y",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            output_audio_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def process_audio(self, audio_path: str) -> List[Dict[str, Any]]:
        model = self.get_model()
        result = model.generate(
            input=audio_path,
            batch_size_s=60,
            sentence_timestamp=True,
        )

        items = result if isinstance(result, list) else [result]
        sentences: List[Dict[str, Any]] = []
        for item in items:
            for sent in item.get("sentence_info", []) or []:
                text = str(sent.get("text", "")).strip()
                start = int(sent.get("start", 0) or 0)
                end = int(sent.get("end", 0) or 0)
                if not text or end <= start:
                    continue
                sentences.append({"text": text, "start": start, "end": end})
        return sentences


asr_service = ASRService()
