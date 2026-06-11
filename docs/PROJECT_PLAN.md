# AI 视频解说剪辑系统项目计划书

## 1. 项目概述

### 1.1 项目名称

AI 视频解说剪辑系统。

### 1.2 项目背景

长视频内容二次创作通常需要人工完成字幕识别、素材理解、文案整理、配音、画面匹配和渲染输出，流程耗时且对剪辑经验要求较高。本项目面向本地单机环境，结合 ASR、LLM、TTS 和 FFmpeg，实现从长视频到解说短视频的半自动化剪辑流程。

### 1.3 项目目标

- 支持用户上传原始视频并生成 ASR 字幕。
- 支持基于用户要求和知识库生成可编辑解说文案。
- 支持人工审核和修改文案 beat。
- 支持 TTS 配音或上传完整配音。
- 支持根据文案和配音时长匹配原视频片段。
- 支持生成 MP4 成片、SRT 字幕和 EDL 工程辅助文件。
- 支持用户、项目、知识库和任务隔离。
- 支持本地 Windows 环境运行和交付。

### 1.4 项目范围

本期实现范围：

- 用户登录、注册和会话管理。
- 项目管理和项目默认配置。
- 项目知识库管理和任务级补充事实。
- 视频任务创建、重生成、删除、查询。
- ASR 字幕识别和缓存。
- LLM 文案初稿生成、定稿文案拆分、人工确认。
- CosyVoice 配音、配音模板、TTS 速度参数。
- LLM 依据全量字幕和配音时长进行选片。
- FFmpeg 渲染成片并输出 SRT、EDL。
- 前端项目工作台、任务详情、事件日志、运行时状态。

本期不实现范围：

- 云端多机部署。
- 可视化拖拽工作流编辑器。
- 高级画面理解、镜头美学评分、B-roll 自动插入。
- Premiere XML、FCPXML、剪映工程导出。
- 多 worker 队列、Celery/Redis 分布式调度。
- 在线时间线精剪编辑器。

## 2. 项目组织

### 2.1 项目成员

项目按三人协作组织，详细职责见 `PROJECT_TEAM_DIVISION.md`。

```text
成员 A：内容理解、知识注入与文案审核闭环
成员 B：配音、选片与成片渲染闭环
成员 C：项目工作台、任务编排与运行状态闭环
```

### 2.2 沟通机制

- 每个功能以任务或 issue 形式记录。
- 每人提交前需要完成本模块自测。
- 主链路修改必须说明对 `raw_subtitles -> draft_beats -> review -> voice -> align -> render` 的影响。
- 涉及 prompt、数据库 schema、API 字段时，需要同步更新文档。

## 3. 技术路线

### 3.1 前端技术

- Vue 3
- Vue Router
- TypeScript
- Vite

### 3.2 后端技术

- Python 3.10+
- FastAPI
- Pydantic
- SQLite
- OpenAI-compatible LLM API
- FunASR
- CosyVoice
- FFmpeg / ffprobe

### 3.3 系统运行方式

当前系统定位为本地 Windows 单机应用。后端监听 `127.0.0.1:8010`，前端开发环境监听 `127.0.0.1:5173`，生产访问可由后端托管 `frontend/dist`。

## 4. 阶段计划

### 4.1 第一阶段：基础框架与本地运行

目标：

- 建立 FastAPI 后端和 Vue 前端。
- 完成视频上传、任务创建、任务状态查询。
- 接入 FFmpeg 基础能力。
- 建立 SQLite 数据库。

交付：

- 可访问的 Web 页面。
- 可创建任务并保存到数据库。
- 基础运行说明。

### 4.2 第二阶段：AI 主链路

目标：

- 接入 FunASR 生成字幕。
- 接入 LLM 生成解说文案。
- 支持文案人工确认。
- 接入 TTS 获取配音时长。
- 接入 LLM 全量字幕选片。
- 接入 FFmpeg 渲染成片。

交付：

- `narration_clip` 默认工作流可跑通。
- 任务结果包含 MP4、SRT、EDL。
- 任务事件日志记录主要阶段。

### 4.3 第三阶段：项目化与用户隔离

目标：

- 增加登录、注册、会话管理。
- 增加项目分类和项目默认配置。
- 增加知识库选择和任务级补充事实。
- 增加受保护文件访问。

交付：

- 用户只能访问自己的项目、知识库、任务和输出文件。
- 前端具备项目工作台和项目设置页面。

### 4.4 第四阶段：配音模板与交付打包

目标：

- 支持 CosyVoice 标准配音和克隆配音模板。
- 支持上传完整配音并按配音 ASR 切分 beat。
- 完善环境检查和 Windows 启动脚本。
- 完成项目文档。

交付：

- 配音模板管理页面。
- Runtime 状态页面。
- 安装、打包、需求、设计、计划和分工文档。

### 4.5 第五阶段：后续增强

目标：

- 引入视觉理解和镜头质量评估。
- 补充专业工程文件导出。
- 引入任务队列和并发控制。
- 完善测试体系。

交付：

- 可选视觉标签进入选片流程。
- FCPXML/Premiere XML 等导出格式。
- 更稳定的多任务调度。

## 5. 里程碑

| 里程碑 | 内容 | 验收方式 |
| --- | --- | --- |
| M1 | 项目可启动 | 后端 `/api/health` 返回正常，前端可打开 |
| M2 | ASR 可用 | 上传视频后生成字幕单元 |
| M3 | 文案可审核 | LLM 生成 draft beats，任务进入 `waiting_review` |
| M4 | 配音可用 | 确认文案后生成 voiceover 音频 |
| M5 | 选片可用 | 返回与 beat 对应的 matched segments |
| M6 | 成片可导出 | 输出 MP4、SRT、EDL |
| M7 | 用户隔离可用 | 登录用户只能访问自己的资源 |
| M8 | 文档可交付 | 三类课程文档和分工文档齐全 |

## 6. 进度现状

当前已完成：

- 后端 FastAPI 基础服务。
- Vue 前端路由页面。
- 用户注册、登录、退出。
- 项目、知识库、任务管理。
- ASR、LLM、TTS、FFmpeg 主链路。
- 草稿审核和任务重生成。
- 工作流模板注册。
- 任务事件日志。
- 受保护文件访问。
- Windows 安装和打包说明。

当前待完善：

- 测试体系较弱，缺少主链路自动化测试。
- 任务队列仍为本地线程，缺少正式并发控制和取消机制。
- 视觉理解和高级剪辑策略未实现。
- 专业工程文件导出不完整。
- 文案事实硬校验和 beat 原子性校验仍需增强。

## 7. 风险分析

| 风险 | 影响 | 应对措施 |
| --- | --- | --- |
| LLM 输出事实漂移 | 文案可能写错方位、角色或事件 | 使用本次补充事实、知识库、grounding、校验和人工审核 |
| LLM 请求超时 | 草稿或选片失败 | 限制上下文、增加超时、保留错误提示和重试入口 |
| TTS 速度慢 | 任务耗时增加 | 缓存音频、支持语速参数、保持 CosyVoice 常驻服务 |
| 本地模型部署复杂 | 交付难度增加 | 使用启动脚本和环境检查文档 |
| 多用户并发任务 | 线程抢占资源，导致卡顿 | 后续引入任务并发上限和队列 |
| 文件存储增长 | 输出、音频、缓存占用磁盘 | 删除任务时清理任务输出，保留可复用缓存策略 |

## 8. 验收计划

### 8.1 功能验收

- 注册新用户并登录。
- 创建项目并配置知识库。
- 上传视频创建 AI 解说任务。
- 生成文案初稿并修改确认。
- 生成配音并完成选片。
- 渲染输出 MP4、SRT、EDL。
- 删除任务并确认资源清理。

### 8.2 工程验收

```bat
cd /d F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app
E:\anaconda\envs\funasr-env\python.exe -c "from app.main import app; print('APP_IMPORT_OK', bool(app))"

cd /d F:\FUNASR\clip_mvp\frontend
npm run build
```

### 8.3 文档验收

- `PROJECT_PLAN.md`
- `SOFTWARE_REQUIREMENTS_SPECIFICATION.md`
- `SYSTEM_DESIGN_DOCUMENT.md`
- `PROJECT_TEAM_DIVISION.md`
- `INSTALL_WINDOWS.md`
- `PACKAGE_WINDOWS.md`

## 9. 交付清单

```text
clip_mvp/app/
clip_mvp/frontend/src/
clip_mvp/scripts/
clip_mvp/docs/
clip_mvp/knowledge/
clip_mvp/requirements.txt
clip_mvp/pyproject.toml
clip_mvp/run.py
clip_mvp/.env.example
```

不交付：

```text
clip_mvp/.env
clip_mvp/data/*.db
clip_mvp/uploads/
clip_mvp/audio/
clip_mvp/outputs/
clip_mvp/frontend/node_modules/
clip_mvp/frontend/dist/
third_party/
```
