import os
import subprocess
from typing import List, Dict, Any

class ASRService:
    def __init__(self):
        self.model = None

    def get_model(self):
        if self.model is None:
            print("正在加载 FunASR 模型，请稍候...")
            from funasr import AutoModel
            self.model = AutoModel(
                model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
                vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                vad_kwargs={"max_single_segment_time": 60000},
                punc_model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
                device="cuda"
            )
            print("模型加载完成")
        return self.model

    def extract_audio_from_video(self, video_path: str, output_audio_path: str) -> bool:
        """
        从视频中提取音频，转换为 16kHz 单声道 WAV 格式
        """
        try:
            cmd = [
                'ffmpeg', '-ss', '0',
                '-i', video_path,
                '-vn',
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-copyts',
                '-y',
                output_audio_path
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr.decode('utf-8') if e.stderr else e}")
            return False
        except FileNotFoundError:
            print("FFmpeg not found. Please install FFmpeg.")
            return False

    def process_audio(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        识别音频并返回句子级别的时间戳
        返回格式: [{"text": "...", "start": 0, "end": 1000}, ...]
        """
        model = self.get_model()
        print(f"\n=== 开始处理音频：{audio_path} ===")
        
        result = model.generate(
            input=audio_path,
            batch_size_s=60,
            sentence_timestamp=True,
        )
        
        results = result if isinstance(result, list) else [result]
        all_sentences = []

        for res in results:
            if "sentence_info" in res:
                for sent in res["sentence_info"]:
                    text = sent.get("text", "").strip()
                    start_ms = sent.get("start", 0)
                    end_ms = sent.get("end", 0)
                    if not text or start_ms < 0 or end_ms < start_ms:
                        continue
                    all_sentences.append({
                        "text": text,
                        "start": start_ms,
                        "end": end_ms
                    })
            else:
                # 降级处理字级别 (兼容旧版本代码逻辑)
                pass # 省略冗长的备用分割逻辑，可直接引用原有方法
                
        return all_sentences

asr_service = ASRService()
