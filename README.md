# ai-video-editing-system

基于 `FunASR + FastAPI + LLM + FFmpeg + Edge TTS` 的智能视频剪辑系统。

## 项目概述

当前版本支持两条核心流程：

1. 文案对齐剪辑
   - 上传视频
   - 提取音频并通过 FunASR 生成句子级时间轴
   - 根据输入文案匹配视频片段
   - 输出粗剪视频和 EDL 工程文件

2. 需求驱动 AI 剪辑
   - 上传视频并输入自然语言需求
   - LLM 根据字幕生成导演总文案、片段选择、逐段配音稿和剪辑建议
   - 可选 AI 重新配音、字幕压制、高亮字幕和模糊特效
   - 输出带字幕/配音的成片

## 当前目录结构

```text
FUNASR/
├── backend/
│   ├── main.py
│   └── app/
│       ├── api/
│       │   └── endpoints/
│       │       └── video.py
│       ├── core/
│       │   └── config.py
│       └── services/
│           ├── advanced_render_service.py
│           ├── asr_service.py
│           ├── export_service.py
│           ├── llm_service.py
│           ├── scriptable_edit_service.py
│           ├── tts_service.py
│           └── video_service.py
├── frontend/
│   └── index.html
├── .env.example
├── .gitignore
└── requirements.txt
```

## 后端说明

- 后端入口：`backend/main.py`
- API 前缀：`/api/v1/video`
- 核心接口：
  - `POST /process_video`
  - `POST /process_video_by_requirements`
- 配置文件：`backend/app/core/config.py`
- 运行依赖：
  - FastAPI 处理 API
  - FunASR 负责 ASR
  - OpenAI SDK 负责对接兼容 OpenAI 协议的 LLM
  - FFmpeg 负责剪辑、拼接、压制字幕
  - edge-tts 负责重新配音

## 前端说明

- 前端文件：`frontend/index.html`
- 采用 CDN 方式加载前端依赖，无需 npm 构建
- 当前使用的前端库：
  - Vue 3
  - Element Plus
  - Axios
  - Element Plus Icons

## 当前环境中检测到的关键版本

以下版本来自你当前的 `funasr-env` 环境：

- `fastapi==0.135.1`
- `uvicorn==0.42.0`
- `openai==2.28.0`
- `pydantic-settings==2.13.1`
- `python-multipart==0.0.22`
- `edge-tts==7.2.8`
- `funasr==1.3.1`
- `modelscope==1.34.0`
- `torch==2.5.1+cu121`
- `torchaudio==2.5.1+cu121`

其中当前实际使用的 FunASR 版本为：

- `funasr==1.3.1`

## 安装说明

### 1. 创建并激活环境

建议使用 Conda：

```bash
conda create -n funasr-env python=3.10 -y
conda activate funasr-env
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 PyTorch

当前开发环境使用的是 CUDA 12.1 版本的 PyTorch：

```bash
pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
```

如果你没有 NVIDIA GPU，可以改用 CPU 版本或你本机对应 CUDA 版本。

### 4. 安装 FFmpeg

本项目依赖本机已安装的 `ffmpeg` 和 `ffprobe`。

安装完成后请确保以下命令可用：

```bash
ffmpeg -version
ffprobe -version
```

## 环境变量

复制 `.env.example` 为 `.env`，并按需填写：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4-turbo-preview
```

说明：

- 根目录 `.env` 会被优先读取
- 若根目录不存在，则后端也支持读取 `backend/.env`

## 启动方式

在项目根目录执行：

```bash
cd backend
python main.py
```

启动后访问：

- `http://127.0.0.1:8000/`

## 主要功能

- 视频上传与音频提取
- 基于 FunASR 的句子级字幕识别
- LLM 驱动的片段选择与导演文案生成
- 文案到片段的语义匹配
- AI 重新配音
- ASS 字幕生成与压制
- 字幕高亮和模糊特效
- EDL 工程导出

## 注意事项

- 当前前端依赖通过 CDN 加载，联网环境下访问更稳定
- 当前 TTS 服务默认调用本机环境中的 `edge-tts`
- 当前 ASR 默认使用 `device="cuda"`，没有 GPU 时需要自行调整为 CPU
- 输出目录、上传目录、音频目录会在运行时自动创建
