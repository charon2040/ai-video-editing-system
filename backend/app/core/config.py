import os
from pydantic_settings import BaseSettings

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_FILE_PATH = os.path.join(_ROOT_DIR, ".env")
if not os.path.exists(ENV_FILE_PATH):
    ENV_FILE_PATH = os.path.join(_BACKEND_DIR, ".env")

class Settings(BaseSettings):
    PROJECT_NAME: str = "Video AI Cut System"
    API_V1_STR: str = "/api/v1"
    
    # 文件存储路径 (这里 __file__ 在 backend/app/core/config.py)
    # dirname(__file__) -> core
    # dirname(dirname(__file__)) -> app
    # dirname(dirname(dirname(__file__))) -> backend
    # dirname(dirname(dirname(dirname(__file__)))) -> F:\FUNASR (根目录)
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    UPLOAD_FOLDER: str = os.path.join(BASE_DIR, 'uploads')
    OUTPUT_FOLDER: str = os.path.join(BASE_DIR, 'output')
    AUDIO_FOLDER: str = os.path.join(BASE_DIR, 'audio')
    
    # 确保目录存在
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(AUDIO_FOLDER, exist_ok=True)

    # LLM 配置
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4-turbo-preview")

    class Config:
        env_file = ENV_FILE_PATH
        env_file_encoding = "utf-8"

settings = Settings()
