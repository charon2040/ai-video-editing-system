# AI 视频解说剪辑系统

AI 视频解说剪辑系统是一个本地运行的 Web 工具，用于把长视频加工成带解说文案、配音、字幕和镜头选择的短视频。系统将 ASR、LLM、TTS、FFmpeg 和人工审核组织成一条可运行、可检查、可重试的工程化工作流。

## 核心流程

```text
上传视频
-> ASR 识别原视频字幕
-> LLM 生成或拆分解说文案
-> 用户人工审核文案
-> TTS 生成配音或接入配音来源
-> LLM 按文案和配音时长选择原视频画面
-> FFmpeg 渲染 MP4、SRT、ASS、EDL
```

系统定位为“字幕和文案驱动的半自动剪辑工具”。AI 负责语义理解、文案生成和片段选择，后端负责状态管理、数据校验、文件处理和最终渲染，用户负责审核关键内容。

## 主要功能

- 用户与项目：支持登录、项目工作台、任务管理和项目级配置。
- 知识库：支持项目知识库、本次补充事实和任务上下文快照。
- 视频任务：支持上传视频、创建任务、查看进度、事件日志和结果下载。
- ASR 字幕：使用 FunASR 识别原视频字幕，并支持基于源文件的缓存。
- 文案生成：结合用户要求、知识库、补充事实和 ASR 字幕生成结构化解说 beats。
- 人工审核：用户确认后的 reviewed beats 作为后续配音和选片依据。
- 配音与选片：按 beat 生成配音，读取真实配音时长，并约束 LLM 选择画面片段。
- 渲染输出：使用 FFmpeg 完成剪切、拼接、混音、单行字幕生成、ASS 字幕烧录和 MP4 输出。
- 运行保障：提供 LLM、ASR、TTS、FFmpeg 等本地依赖的状态探测和错误定位能力。

## 技术栈

### 前端

- Vue 3
- TypeScript
- Vite
- Vue Router

### 后端

- Python 3.10+
- FastAPI
- SQLite
- 本地后台 worker

### AI 与媒体工具

- FunASR：原视频字幕识别
- OpenAI-compatible LLM：文案生成、结构修复、语义选片
- CosyVoice / TTS provider：配音生成
- FFmpeg / ffprobe：抽音频、剪切、拼接、混音、字幕烧录和媒体探测

## 项目结构

```text
clip_mvp/
  app/                 后端 FastAPI 应用
  frontend/            前端 Vue 应用
  docs/                架构文档、项目说明、答辩 HTML
  scripts/             本地启动和检查脚本
  knowledge/           示例知识文件
  static/              静态资源
  uploads/             本地上传文件目录，不应提交真实素材
  outputs/             本地输出结果目录，不应提交生成视频
  data/                SQLite、缓存和运行数据，不应提交
```

## 本地运行

### 1. 后端

```powershell
cd F:\FUNASR\clip_mvp
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8010
```

如果使用已有 Conda 环境，可以直接在对应环境中安装依赖并启动后端。

### 2. 前端

```powershell
cd F:\FUNASR\clip_mvp\frontend
npm install
npm run dev
```

前端默认通过 Vite 启动，浏览器访问终端输出的本地地址。

## 配置说明

复制示例配置并按本地环境填写：

```powershell
cd F:\FUNASR\clip_mvp
Copy-Item .env.example .env
```

`.env` 中通常需要配置 LLM API 地址、模型名称、密钥、ASR/TTS/FFmpeg 相关路径或服务地址。真实 `.env` 不应提交到 Git。

## 输出文件

任务完成后，系统可输出：

- `final.mp4`：最终成片
- `subtitle.srt`：通用字幕文件
- `subtitle.ass`：用于字幕样式和烧录的 ASS 字幕
- `decision.edl`：剪辑决策文件，记录选片结果

## 答辩材料

项目总答辩 HTML 位于：

```text
clip_mvp/docs/full_project_defense_slides.html
```

配套项目讲解文档位于：

```text
clip_mvp/docs/PROJECT_EXPLAINED.md
clip_mvp/docs/DEFENSE_SCRIPT_FULL_PROJECT.md
```

## 仓库注意事项

以下内容不应提交到 Git：

- `.env` 和任何密钥配置
- 数据库、缓存和日志
- 上传视频、生成音频、输出视频
- `node_modules/`、前端构建产物和本地模型权重

提交代码前建议检查：

```powershell
git status --short
python -m compileall clip_mvp\app
cd clip_mvp\frontend
npm run build
```
