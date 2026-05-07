# FUNASR AI 视频剪辑系统

基于 `FunASR + FastAPI + Vue 3 + Vite + FFmpeg + Edge TTS + LLM` 的一体化 AI 视频剪辑系统。

本项目不是单纯的“后端出片工具”，也不是纯前端剪辑器，而是：

- 前端负责实时编辑、预览、时间线交互和高级导出。
- 后端负责项目持久化、素材托管、AI 剪辑、ASR、TTS、后端 FFmpeg 渲染与导出任务。

## 项目现状

当前代码已经收敛为“源码直跑”模式：

- 前端唯一源码目录是 `frontend/`
- 后端唯一服务目录是 `backend/`
- 当前仅保留简体中文 `zh-CN`
- AI 剪辑结果会写入后端项目时间线，并可继续在前端编辑

## 两条核心流程

### 1. 文案对齐剪辑

- 上传视频
- 后端抽取音频
- FunASR 生成句子级字幕时间轴
- LLM 按输入文案从字幕中匹配片段
- 输出粗剪视频和 EDL 工程文件

### 2. 需求驱动 AI 剪辑 / AI 重配音

- 上传视频并输入自然语言需求
- Round 1：LLM 先生成导演总文案和逐段解说稿
- 本地 TTS：逐段配音并测得每段真实时长
- Round 2：LLM 根据真实 TTS 时长选择对应画面区间
- 后端强制把真实 TTS 时长与音频按 `segment_index` 回填
- FFmpeg 直接输出整条 AI 成片，并生成可继续编辑的时间线源视频
- AI 结果自动写入后端项目时间线，前端可继续微调

## 关键输出文件说明

AI 重配音流程通常会在 `output/` 下生成几类文件：

- `*_cut.mp4`
  - 拼接完成但未压最终字幕的中间成片
- `*_redub.mp4`
  - 带 AI 配音和字幕的最终 AI 成片
- `*_timeline_source.mp4`
  - 提供给前端时间线继续编辑的源视频
- `export_job_*.mp4`
  - 后端导出任务队列完成后的正式导出文件
- `*.edl`
  - 可供外部剪辑软件导入的 EDL 工程文件

## 目录结构

```text
FUNASR/
├── backend/                  # FastAPI 后端
│   ├── main.py               # 推荐启动入口
│   └── app/
│       ├── api/              # AI / 项目 / 时间线 / 导出接口
│       ├── core/             # 配置
│       ├── db/               # SQLite 初始化
│       ├── schemas/          # Pydantic 模型
│       └── services/         # ASR / LLM / TTS / FFmpeg / 项目编排
├── frontend/                 # Vue 3 + Vite 前端源码
│   ├── src/
│   │   ├── hooks/            # 前后端同步、播放器、状态管理
│   │   ├── libs/             # API / ffmpeg / 工具
│   │   ├── modules/          # 高级导出、动画、滤镜、转场
│   │   └── views/            # 编辑器、素材库、AI 面板、时间线
│   ├── package.json
│   └── vite.config.ts
├── audio/                    # 抽音频与中间音频
├── data/                     # SQLite 数据库
├── output/                   # 后端生成结果
├── uploads/                  # 上传素材
├── .env.example
├── requirements.txt
└── PROJECT_ARCHITECTURE.md
```

## 环境要求

建议使用以下环境：

- Windows
- Conda 环境：`funasr-env`
- Python 3.10
- Node.js 18+
- 已安装 `ffmpeg` 和 `ffprobe`

## Python 关键依赖

当前项目实际依赖的核心组件包括：

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

## 安装步骤

### 1. 创建并激活 Conda 环境

```bash
conda create -n funasr-env python=3.10 -y
conda activate funasr-env
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 安装 PyTorch

如果你使用 CUDA 12.1，可参考：

```bash
pip install torch==2.5.1+cu121 torchaudio==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121
```

没有 NVIDIA GPU 时，请改为适合你机器的 CPU 版或对应 CUDA 版。

### 4. 安装 FFmpeg

确认以下命令可在终端直接执行：

```bash
ffmpeg -version
ffprobe -version
```

### 5. 安装前端依赖

```bash
cd frontend
pnpm install
```

## 环境变量

复制 `.env.example` 为 `.env`，并按需填写：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4-turbo-preview
```

说明：

- 根目录 `.env` 优先级高于 `backend/.env`
- 如果未配置 `LLM_API_KEY`，部分 LLM 相关流程无法正常执行

## 启动方式

### 1. 启动后端

在项目根目录执行：

```bash
conda activate funasr-env
cd backend
python main.py
```

默认监听：

- `http://127.0.0.1:8000`

后端会挂载以下静态资源：

- `/uploads/*`
- `/download/*`
- `/audio/*`

### 2. 启动前端

在项目根目录执行：

```bash
cd frontend
pnpm run dev
```

前端通过 Vite 代理访问后端 API 与静态资源。

## 主要接口

### 旧视频处理接口

- `POST /api/v1/process_video`
- `POST /api/v1/process_video_by_requirements`

### 编辑器接口

- `POST /api/v1/editor/ai/generate`
- `GET /api/v1/editor/projects`
- `GET /api/v1/editor/projects/{project_id}`
- `PUT /api/v1/editor/projects/{project_id}/timeline`
- `POST /api/v1/editor/projects/{project_id}/exports`
- `GET /api/v1/editor/projects/{project_id}/exports/{job_id}`

## 前后端职责边界

### 前端负责

- 时间线交互
- 素材预览与实时播放
- 拖拽、裁剪、分割、转场、属性编辑
- 高级导出模块
- 把当前编辑状态同步到后端

### 后端负责

- 项目 / 时间线 / 资产持久化
- ASR 识别
- LLM 生成文案与选段
- 本地 TTS 测时与正式配音复用
- 后端 FFmpeg 粗剪、红配、字幕压制
- 导出任务排队与结果产出

## 当前 AI 重配音的真实逻辑

当前红配音不是“LLM 估时直接出片”，而是：

1. `generate_redub_outline()` 生成总文案与逐段文案
2. `synthesize_segments_with_duration()` 对逐段文案本地 TTS，得到真实毫秒时长
3. `generate_timed_redub_segments()` 只负责选择原视频画面区间
4. 后端按 `segment_index` 回填真实 `tts_duration_ms` 与 probe 音频
5. 后端再对过长或过短片段做强约束修正
6. FFmpeg 单次拼出整条视频，不再逐段先生成一堆临时 mp4

## 当前编辑器接入方式

AI 面板走的是：

- `POST /api/v1/editor/ai/generate`

该流程会：

- 生成 AI 结果
- 把 AI 片段、字幕轨、配音轨写入后端项目时间线
- 注册 `AI成片`、`时间线源视频`、`AI配音音轨` 资产
- 前端再从后端项目回灌到编辑器，继续编辑

## 注意事项

- 当前界面语言固定为简体中文
- `edge-tts` 路径需要在本机可用
- FunASR 默认优先走 GPU，没有 GPU 时需确认相关配置
- `output/`、`uploads/`、`audio/`、`data/` 会在运行时自动创建
- 若修改了后端 Python 代码，通常需要重启后端进程
