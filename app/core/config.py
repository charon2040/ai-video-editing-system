from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    project_name: str = "Clip MVP"
    api_prefix: str = "/api"

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 180
    narration_chars_per_second_min: float = 3.2
    narration_chars_per_second_max: float = 5.2

    funasr_device: str = "auto"
    funasr_model: str = "iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    funasr_vad_model: str = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    funasr_punc_model: str = "iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch"

    tts_provider: str = "cosyvoice"
    tts_default_mode: str = "standard"
    tts_standard_provider: str = "cosyvoice"
    tts_clone_provider: str = "cosyvoice"
    tts_timeout_seconds: int = 120
    tts_http_read_timeout_seconds: int = 300
    tts_default_voice: str = "中文女"
    tts_keep_original_audio_default: bool = True
    tts_original_audio_volume: float = 0.18
    tts_speed_default: float = 1.0
    tts_speed_min: float = 0.8
    tts_speed_max: float = 1.25
    tts_chunk_soft_chars: int = 60
    tts_chunk_hard_chars: int = 90
    tts_profile_manifest_path: str = str(BASE_DIR / "data" / "tts_profiles.json")
    cosyvoice_service_startup_seconds: int = 120
    cosyvoice_local_python: str = str(BASE_DIR.parent / "third_party" / "cosyvoice-env-win" / "python.exe")
    cosyvoice_repo_dir: str = str(BASE_DIR.parent / "third_party" / "CosyVoice")
    cosyvoice_model_dir: str = str(BASE_DIR.parent / "third_party" / "models" / "Fun-CosyVoice3-0.5B")
    cosyvoice_cache_dir: str = str(BASE_DIR.parent / "third_party" / "hf_cache")
    cosyvoice_base_url: str = "http://127.0.0.1:50000"
    cosyvoice_sft_endpoint: str = "/inference_sft"

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def upload_dir(self) -> Path:
        return BASE_DIR / "uploads"

    @property
    def audio_dir(self) -> Path:
        return BASE_DIR / "audio"

    @property
    def output_dir(self) -> Path:
        return BASE_DIR / "outputs"

    @property
    def voiceover_dir(self) -> Path:
        return self.output_dir / "voiceovers"

    @property
    def project_dir(self) -> Path:
        return BASE_DIR

    @property
    def helper_dir(self) -> Path:
        return BASE_DIR / "app" / "tools"

    @property
    def cosyvoice_helper_path(self) -> Path:
        return self.helper_dir / "cosyvoice_local_helper.py"

    @property
    def cosyvoice_service_path(self) -> Path:
        return self.helper_dir / "cosyvoice_local_server.py"

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"

    @property
    def tts_profile_manifest(self) -> Path:
        return Path(self.tts_profile_manifest_path)

    @property
    def tts_runtime_profile_manifest(self) -> Path:
        return self.data_dir / "tts_profiles.runtime.json"

    @property
    def tts_profile_audio_dir(self) -> Path:
        return self.data_dir / "tts_profiles"

    @property
    def tts_user_profile_audio_dir(self) -> Path:
        return self.tts_profile_audio_dir / "user"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def cosyvoice_service_stdout_log(self) -> Path:
        return self.data_dir / "cosyvoice-service.out.log"

    @property
    def cosyvoice_service_stderr_log(self) -> Path:
        return self.data_dir / "cosyvoice-service.err.log"

    @property
    def static_dir(self) -> Path:
        return BASE_DIR / "static"

    @property
    def frontend_dist_dir(self) -> Path:
        return BASE_DIR / "frontend" / "dist"

    @property
    def task_store_path(self) -> Path:
        return self.data_dir / "tasks.json"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "clip_mvp.db"

    @property
    def misplaced_database_path(self) -> Path:
        return BASE_DIR / "app" / "data" / "clip_mvp.db"


settings = Settings()


def ensure_runtime_dirs() -> None:
    for path in (
        settings.upload_dir,
        settings.audio_dir,
        settings.output_dir,
        settings.voiceover_dir,
        settings.helper_dir,
        settings.data_dir,
        settings.static_dir,
        settings.tts_profile_audio_dir,
        settings.tts_user_profile_audio_dir,
        settings.temp_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
