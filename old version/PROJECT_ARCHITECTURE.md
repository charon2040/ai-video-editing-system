# WebCut / FUNASR 前后端架构说明

## 1. 项目定位

本项目是一个“前端实时编辑 + 后端 AI/持久化/渲染”的一体化视频剪辑系统。

- 前端负责交互、预览、时间线编辑和高级导出。
- 后端负责项目状态、素材托管、ASR、LLM、TTS、FFmpeg 渲染和导出任务。

当前代码已经统一到 `frontend/` + `backend/` 两个主目录，按源码直接运行，不再依赖旧的打包产物目录。

## 2. 总体原则

### 2.1 前端负责什么

- 素材导入与本地预览
- 时间线拖拽、分割、拼接、转场、属性编辑
- WebAV 实时渲染
- 浏览器内高级导出
- 把编辑状态同步到后端

### 2.2 后端负责什么

- 项目 / 时间线 / 资产持久化
- 上传文件与输出文件托管
- FunASR 语音识别
- LLM 文案生成和选段
- Edge TTS 配音与时长测量
- 后端 FFmpeg 粗剪、重配音、字幕压制、导出队列

### 2.3 当前单语言策略

- 国际化当前只保留简体中文 `zh-CN`
- 前端 `i18n` 已收缩为单语言模式
- 不再保留语言切换入口

## 3. 根目录说明

### 3.1 顶层目录

- `backend/`
  - FastAPI 后端源码
- `frontend/`
  - Vue 3 + Vite 前端源码
- `data/`
  - SQLite 数据库目录，主库为 `studio.db`
- `uploads/`
  - 上传素材目录
- `output/`
  - 后端 AI 与导出结果目录
- `audio/`
  - 抽取音频与中间音频目录
- `documents/`
  - 项目内部说明文档
- `docs/`
  - 原 WebCut 文档站遗留目录

### 3.2 顶层文件

- `.env.example`
  - 环境变量示例
- `README.md`
  - 对外使用说明
- `PROJECT_ARCHITECTURE.md`
  - 架构说明
- `requirements.txt`
  - Python 依赖
- `start_backend.bat`
  - Windows 下后端快捷启动脚本
- `start_frontend.bat`
  - Windows 下前端快捷启动脚本

## 4. 运行与资源流向

### 4.1 启动方式

- 前端：`frontend/` 下运行 `pnpm run dev`
- 后端：`backend/` 下运行 `conda activate funasr-env` 后执行 `python main.py`

### 4.2 请求流向

1. 浏览器访问 Vite 开发服务器
2. 前端通过 `/api/*` 访问 FastAPI
3. 前端通过 `/uploads/*`、`/download/*`、`/audio/*` 访问后端静态媒体
4. 前端修改时间线后调用后端接口保存项目状态
5. AI 任务和导出任务由后端真正落盘生成文件

### 4.3 输出文件类型

AI 重配音流程下常见输出如下：

- `*_cut.mp4`
  - 拼接后但未做最终字幕压制的视频
- `*_redub.mp4`
  - AI 红配音最终成片
- `*_timeline_source.mp4`
  - 给前端时间线继续编辑使用的源视频
- `export_job_*.mp4`
  - 后端导出任务完成后的正式渲染结果
- `*.edl`
  - 外部剪辑软件可导入的 EDL 文件

## 5. 后端结构

后端核心目录为 `backend/app/`。

### 5.1 入口与配置

- `backend/main.py`
  - 当前主要启动入口
  - 创建 FastAPI 应用
  - 注册编辑器路由
  - 挂载 `/download`、`/uploads`
- `backend/app/main.py`
  - 应用模块入口
  - 注册 `/api/v1` 与 `/api/v1/editor`
  - 挂载 `/uploads`、`/download`、`/audio`
  - 适合模块化运行
- `backend/app/core/config.py`
  - 全局配置中心
  - 定义 `UPLOAD_FOLDER`、`OUTPUT_FOLDER`、`AUDIO_FOLDER`、`DATABASE_PATH`

### 5.2 数据库与模型

- `backend/app/db/database.py`
  - SQLite 初始化与连接管理
- `backend/app/schemas/studio.py`
  - 项目、时间线、导出等接口的请求模型

### 5.3 API 路由

- `backend/app/api/endpoints/video.py`
  - 旧视频处理与 AI 主流程入口
  - 仍然是 AI 自动剪辑与 AI 红配音的核心编排文件
- `backend/app/api/editor/ai.py`
  - 编辑器侧 AI 入口
  - 接收上传文件、需求、是否启用红配音
  - 最终调用 `process_video_to_project()`
- `backend/app/api/editor/projects.py`
  - 项目与素材管理
- `backend/app/api/editor/timeline.py`
  - 时间线增删改查、片段操作、轨道操作、历史记录
- `backend/app/api/editor/exports.py`
  - 导出任务创建与状态查询

### 5.4 关键服务文件

- `backend/app/services/asr_service.py`
  - FunASR 识别与音频抽取相关流程
- `backend/app/services/llm_service.py`
  - LLM 相关逻辑
  - 包括普通需求剪辑、红配音 Round 1 / Round 2 提示词与解析
- `backend/app/services/tts_service.py`
  - Edge TTS 封装
  - 支持逐段配音和真实时长测量
- `backend/app/services/video_service.py`
  - FFmpeg 视频处理服务
  - 当前红配逻辑已改为单次 FFmpeg concat filter 输出整片
- `backend/app/services/advanced_render_service.py`
  - 高级渲染与 ASS 字幕压制
- `backend/app/services/editor_ai_orchestrator.py`
  - 把 AI 结果写入后端项目、时间线、资产与导出任务
- `backend/app/services/editor_project_service.py`
  - 项目与资产服务封装
- `backend/app/services/editor_timeline_service.py`
  - 时间线服务封装
- `backend/app/services/editor_export_service.py`
  - 导出服务封装
- `backend/app/services/render_queue_service.py`
  - 导出队列后台线程
- `backend/app/services/studio_service.py`
  - 数据与路径协调总入口

## 6. AI 剪辑主流程

### 6.1 普通 AI 剪辑

入口：

- `POST /api/v1/process_video_by_requirements`
- `POST /api/v1/editor/ai/generate`

流程：

1. 保存上传视频
2. 抽取音频
3. FunASR 识别字幕
4. LLM 生成导演文案、建议、片段
5. FFmpeg 按片段拼接粗剪视频
6. 可选压制字幕与特效
7. 返回 `output_video_url`、`matched_segments` 等结果

### 6.2 AI 红配音流程

入口仍然是：

- `POST /api/v1/process_video_by_requirements`
- `POST /api/v1/editor/ai/generate`

但开启 `enable_redub=true` 后逻辑不同：

1. `generate_redub_outline()`
  - 第一轮只生成总文案和逐段解说稿
2. `synthesize_segments_with_duration()`
  - 本地 TTS 生成每段音频
  - 计算每段真实 `tts_duration_ms`
  - 保留 probe 音频用于后续正式合成复用
3. `generate_timed_redub_segments()`
  - 第二轮只负责基于真实 TTS 时长选择视频区间
4. `bind_measured_tts_to_segments()`
  - 按 `segment_index` 把真实音频和真实时长回填到第二轮结果
5. `ensure_redub_segments_cover_tts()`
  - 后端对片段长度做强约束
  - 既防止片段短于 TTS，也防止明显超长
6. `cut_and_concat_video_with_redub()`
  - 从原视频取画面
  - 复用第一轮 TTS 音频
  - 直接一次 FFmpeg 输出整条 AI 红配音视频
7. `advanced_render_service.generate_ass_subtitle()`
  - 生成红配字幕并压制

### 6.3 红配输出的几个 URL 含义

- `output_video_url`
  - 最终 AI 成片，通常是 `*_redub.mp4`
- `timeline_source_video_url`
  - 用于前端继续编辑的时间线源视频，通常是 `*_timeline_source.mp4`
- `voiceover_audio_url`
  - AI 配音主轨音频

## 7. AI 结果如何写入项目时间线

核心文件是 `backend/app/services/editor_ai_orchestrator.py`。

### 7.1 写入逻辑

AI 流程完成后，`finalize_ai_result_to_project()` 会：

1. 确定目标项目
  - 若前端传了 `project_id`，写入当前项目
  - 否则新建 AI 项目
2. 构造时间线
  - 视频轨：使用 `matched_segments`
  - 字幕轨：使用 `dubbing` 或 `content`
  - 音频轨：在红配模式下挂载 `voiceover_audio_url`
3. 注册资产
  - `AI成片`
  - `时间线源视频`
  - `AI配音音轨`
4. 按需创建导出任务

### 7.2 为什么前端还能继续编辑

因为写入时间线时并不是只返回一个成片 URL，而是把结构化片段写进了后端项目：

- 视频片段轨
- 字幕轨
- AI 配音音轨

前端只需要重新从该项目回灌时间线，就能继续编辑。

## 8. 前端结构

前端核心目录是 `frontend/src/`。

### 8.1 关键入口

- `frontend/src/webcomponents.ts`
  - Web Components 注册入口
- `frontend/src/views/editor/index.vue`
  - 编辑器主页面
- `frontend/src/views/library/index.vue`
  - 素材库主页面
- `frontend/src/views/manager/index.vue`
  - 时间线主页面

### 8.2 关键 hooks

- `frontend/src/hooks/backend-sync.ts`
  - 前后端时间线同步核心
  - 负责后端项目回灌到前端时间线
  - 负责前端时间线更新回写到后端
- `frontend/src/hooks/ai-preview.ts`
  - AI 结果预览状态
- `frontend/src/hooks/library.ts`
  - 素材库与后端项目联动
- `frontend/src/hooks/manager.ts`
  - 时间线片段交互逻辑

### 8.3 关键前端适配层

- `frontend/src/libs/editor-backend.ts`
  - 后端 API 适配层
  - 负责：
  - 项目列表 / 详情
  - 时间线保存
  - 导出任务查询
  - 后端文件 URL 归一化

### 8.4 AI 面板

- `frontend/src/views/library/ai/index.vue`
  - AI 面板入口
  - 当前调用 `POST /api/v1/editor/ai/generate`
  - 会把当前激活项目 ID 一并提交给后端
  - AI 完成后会主动切换到目标后端项目并回灌时间线

### 8.5 高级导出

- `frontend/src/modules/advanced-export/`
  - 浏览器侧高级导出模块
  - 与后端 AI 成片不是同一条链路
  - 适合用户在时间线继续微调后进行最终浏览器导出

## 9. 前后端数据主线

### 9.1 项目状态

当前“项目真值”主要在后端数据库中：

- 项目
- 资产
- 时间线
- 轨道
- 片段
- 历史记录
- 导出任务

前端保留本地缓存，但已不是唯一真值来源。

### 9.2 时间线同步

同步机制大致为：

1. 前端加载项目时从后端拉取时间线
2. 用户操作时间线时先更新前端即时状态
3. `backend-sync.ts` 负责把结构化结果写回后端
4. AI 生成后再从后端项目回灌到前端时间线

## 10. 当前需要知道的现实边界

### 10.1 后端能做什么

- AI 剪辑
- AI 红配音成片
- 后端导出任务
- 项目与时间线持久化

### 10.2 后端不能完全替代前端什么

- 前端的实时所见即所得交互
- 浏览器内高级导出交互体验
- 用户手工细调时的即时预览与操作反馈

### 10.3 当前推荐的实际用法

最合理的工作流是：

1. 在 AI 面板生成初版
2. 让后端产出 AI 成片和时间线源视频
3. 自动写入当前项目时间线
4. 在前端继续微调
5. 最终用前端高级导出或后端导出任务输出成片

## 11. 关键文件速查

### 11.1 后端

- `backend/main.py`
- `backend/app/main.py`
- `backend/app/api/endpoints/video.py`
- `backend/app/api/editor/ai.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/tts_service.py`
- `backend/app/services/video_service.py`
- `backend/app/services/editor_ai_orchestrator.py`
- `backend/app/services/advanced_render_service.py`

### 11.2 前端

- `frontend/src/views/library/ai/index.vue`
- `frontend/src/hooks/backend-sync.ts`
- `frontend/src/libs/editor-backend.ts`
- `frontend/src/views/editor/index.vue`
- `frontend/src/views/manager/container/index.vue`
- `frontend/src/modules/advanced-export/index.vue`
- `frontend/src/i18n/core.ts`

## 12. 当前版本结论

当前系统已经形成如下稳定职责划分：

- 前端是交互层和实时编辑层
- 后端是项目状态层、AI 处理层和落盘渲染层
- AI 红配音已经采用“两轮 LLM + 本地 TTS 真时长绑定 + 单次 FFmpeg 成片”
- AI 结果不只是返回一个视频链接，而是会写入项目时间线供后续继续编辑

#### `views/tools/`

- `clear/index.vue`
  - 清空工具。
- `concat/index.vue`
  - 拼接工具。
- `delete/index.vue`
  - 删除工具。
- `flip-h/index.vue`
  - 水平翻转工具。
- `history-recover/index.vue`
  - 历史恢复工具。
- `redo/index.vue`
  - 重做工具。
- `split/index.vue`
  - 分割工具。
- `split-keep-left/index.vue`
  - 分割后保留左侧工具。
- `split-keep-right/index.vue`
  - 分割后保留右侧工具。
- `undo/index.vue`
  - 撤销工具。

#### 其他视图组件

- `loading/index.vue`
  - 全局加载状态。
- `provider/index.vue`
  - 全局 Provider，挂载 naive-ui 等上下文。
- `reset-button/index.vue`
  - 重置项目按钮。
- `select-aspect-ratio/index.vue`
  - 画幅比例选择。
- `theme-box/index.vue`
  - 主题容器。
- `theme-switch/index.vue`
  - 主题切换。
- `time-clock/index.vue`
  - 时间显示组件。
- `toast/index.vue`
  - 提示组件。

### 5.13 `frontend/src/types/`

- `index.ts`
  - 前端核心类型定义。
  - 包括上下文、轨道、片段、素材、面板、扩展接口等类型。

### 5.14 其他源码文件

- `img/effect-icons.jpg`
  - 效果图标图集。
- `img/rotate.svg`
  - 旋转图标。
- `img/transition-sprite.jpg`
  - 转场图集。
- `styles/export-button.less`
  - 高级导出按钮样式。
- `styles/form.less`
  - 表单样式。
- `styles/library.less`
  - 素材库样式。
- `vite-env.d.ts`
  - Vite 环境类型声明。
- `vue-shims.d.ts`
  - Vue 单文件组件类型声明。

---

## 6. 前后端关系，精确到代码文件

### 6.1 素材上传链路

1. 前端在 `views/library/_shared/import.vue` 中接收文件。
2. 若不是 mp4，则通过 `libs/ffmpeg.ts` 在浏览器里转码。
3. 通过 `libs/editor-backend.ts` 调用后端 `api/editor/projects.py` 的上传接口。
4. 后端写入 `uploads/`，并由 `studio_service.py` 生成 `download_url`。
5. 前端素材库 `hooks/library.ts` 拉取资产列表并渲染。

### 6.2 素材加入时间线链路

1. `views/library/_shared/list.vue` 点击添加。
2. `hooks/index.ts` 的 `push()` 根据素材类型构造 `MP4Clip`、`AudioClip`、`ImgClip`。
3. 本地播放器立即渲染预览。
4. 后续通过 `hooks/backend-sync.ts` 或相关操作函数同步到后端。

### 6.3 时间线历史链路

1. 前端 `hooks/history.ts` 管理当前操作记录。
2. 后端 `studio_history_ops.py` 管理可持久化的历史栈。
3. API 入口是 `api/editor/timeline.py` 中的 `/history/*` 路由。

### 6.4 导出链路

1. 前端 `modules/advanced-export/*` 组织导出参数。
2. `libs/editor-backend.ts` 调 `/projects/{id}/exports`。
3. 后端 `editor_export_service.py`、`studio_export_ops.py`、`render_queue_service.py` 组织任务。
4. `advanced_render_service.py` 根据时间线构建 FFmpeg 命令并输出到 `output/`。

### 6.5 AI 剪辑链路

1. 前端 `views/library/ai/index.vue` 提交 AI 请求。
2. 后端 `api/editor/ai.py` 收请求。
3. `video.py` + `editor_ai_orchestrator.py` 编排 ASR、LLM、TTS。
4. 结果写回项目、素材、时间线表。

---

## 7. 当前结构下的重点结论

- 前端实时预览靠 `frontend/src/hooks/index.ts` + WebAV。
- 后端状态真源靠 `backend/app/services/studio_service.py` + SQLite。
- 前端素材请求统一走 `libs/editor-backend.ts`。
- 后端素材 URL 统一通过 `studio_service.py` 转换成 `/uploads/*` 或 `/download/*`。
- 浏览器端文件缓存只在 `frontend/src/db/index.ts` 和 `hooks/local-file.ts` 处理。
- 当前项目已经不再依赖旧的前端 bundle 目录，开发与调试应直接围绕 `frontend/` 和 `backend/app/` 进行。

---

## 8. 全量文件清单版

这一节按**当前真实目录**逐文件列出职责，目标是做到查到文件名就能知道它的用途。

### 8.1 后端 `backend/app/` 全量文件

#### 包入口与基础层

- `backend/app/__init__.py`：`app` 包初始化文件。
- `backend/app/main.py`：FastAPI 启动入口，挂载 API 路由与静态资源目录。
- `backend/app/core/config.py`：后端配置中心，统一管理根目录、数据库、上传目录、输出目录、音频目录。
- `backend/app/db/__init__.py`：数据库子包初始化。
- `backend/app/db/database.py`：SQLite 初始化、建表、连接工厂。
- `backend/app/schemas/__init__.py`：Pydantic schema 包初始化。
- `backend/app/schemas/studio.py`：项目、素材、时间线、导出相关请求模型定义。

#### API 聚合层

- `backend/app/api/__init__.py`：API 包初始化。
- `backend/app/api/endpoints/__init__.py`：聚合 endpoint 包初始化。
- `backend/app/api/endpoints/editor.py`：聚合 `editor` 子路由到统一入口。
- `backend/app/api/endpoints/video.py`：旧视频处理与 AI 自动剪辑主入口，仍承担 AI 长链路调用。

#### 编辑器 API 层

- `backend/app/api/editor/__init__.py`：聚合项目、时间线、导出、AI 路由。
- `backend/app/api/editor/common.py`：项目存在性校验、时长探测、路径解析等公共工具。
- `backend/app/api/editor/projects.py`：项目创建、项目详情、素材上传、素材注册、素材删除、项目重置、失效素材清理。
- `backend/app/api/editor/timeline.py`：时间线读写、撤销重做、片段 patch、分割、拼接、翻转、轨道 patch、转场应用、波纹删除。
- `backend/app/api/editor/exports.py`：导出任务创建、列表查询、单任务状态查询。
- `backend/app/api/editor/ai.py`：AI 剪辑入口，接收上传文件和要求并触发自动生成项目。

#### 业务服务层

- `backend/app/services/studio_service.py`：后端总协调器，负责项目、素材、时间线、导出、路径映射、重置清理。
- `backend/app/services/editor_project_service.py`：项目/素材服务门面，对 API 层暴露统一调用方法。
- `backend/app/services/editor_timeline_service.py`：时间线服务门面，封装时间线与历史操作。
- `backend/app/services/editor_export_service.py`：导出服务门面，封装导出任务创建与查询。
- `backend/app/services/editor_ai_orchestrator.py`：AI 流程总编排器，协调 ASR、LLM、TTS 与项目写回。
- `backend/app/services/editor_logic_registry.py`：前后端共识逻辑注册表，保存滤镜、动画、转场等 preset 元数据。
- `backend/app/services/studio_timeline_core_ops.py`：时间线整体结构的底层操作，例如轨道/片段组装与主时间线写入。
- `backend/app/services/studio_timeline_clip_ops.py`：片段级操作，负责创建、删除、拆音频、拼接、翻转等。
- `backend/app/services/studio_timeline_track_ops.py`：轨道级操作，负责创建、删除、排序、锁定、静音、显示。
- `backend/app/services/studio_transition_ops.py`：转场应用、清除与转场相关时间线写回。
- `backend/app/services/studio_history_ops.py`：时间线历史栈，负责撤销、重做、恢复。
- `backend/app/services/studio_export_ops.py`：导出底层操作与导出作业组织。
- `backend/app/services/render_queue_service.py`：导出任务排队与任务状态管理。
- `backend/app/services/advanced_render_service.py`：高质量导出渲染核心，拼装 FFmpeg filter graph，处理字幕、滤镜、图层、音视频混流。
- `backend/app/services/video_service.py`：通用视频处理工具服务，封装 FFmpeg/ffprobe。
- `backend/app/services/export_service.py`：旧导出封装，兼容部分历史调用。
- `backend/app/services/asr_service.py`：语音识别服务，对接 FunASR 或其他 ASR 引擎。
- `backend/app/services/llm_service.py`：大模型服务，负责需求理解、脚本生成、片段筛选等。
- `backend/app/services/tts_service.py`：语音合成服务，负责配音生成。

### 8.2 前端 `frontend/src/` 全量文件

#### 顶层入口文件

- `frontend/src/index.ts`：前端总导出文件，统一导出组件、hooks、工具函数、DB 能力和类型。
- `frontend/src/webcomponents.ts`：自定义元素注册入口，把 Vue 组件注册成 `<webcut-editor>` 等 Web Components。
- `frontend/src/vite-env.d.ts`：Vite 环境类型声明。
- `frontend/src/vue-shims.d.ts`：Vue 单文件组件类型声明。

#### 常量层

- `frontend/src/constants/index.ts`：常量定义，当前核心是画幅比例映射等基础配置。

#### 浏览器端数据层

- `frontend/src/db/index.ts`：IndexedDB 与 OPFS 封装，负责文件缓存、项目状态、历史记录与本地清理。

#### hooks 层

- `frontend/src/hooks/index.ts`：前端核心运行时上下文，管理播放器、轨道、素材源、时间轴状态和渲染对象。
- `frontend/src/hooks/ai-preview.ts`：AI 预览相关状态与展示逻辑。
- `frontend/src/hooks/backend-sync.ts`：前后端同步逻辑，把前端时间线操作转成 API 请求。
- `frontend/src/hooks/history.ts`：前端历史记录 hook，组织本地 Undo/Redo 行为。
- `frontend/src/hooks/library.ts`：素材库数据 hook，负责读取后端素材列表、上传新素材、删除素材。
- `frontend/src/hooks/local-file.ts`：本地文件与后端素材 URL 解析层，优先读取后端地址，必要时回退本地缓存。
- `frontend/src/hooks/manager.ts`：时间线管理 hook，处理轨道、片段、选中状态和拖拽操作。
- `frontend/src/hooks/toast.ts`：全局 Toast 状态管理。
- `frontend/src/hooks/transition.ts`：转场交互与转场状态 hook。

#### 国际化层

- `frontend/src/i18n/core.ts`：国际化配置入口，当前仅保留简体中文标签与单语言定义。
- `frontend/src/i18n/hooks/index.ts`：`useT()`、`useWebCutLocale()` 等国际化 hooks，当前语言固定为 `zh-CN`。

#### 通用工具层 `libs/`

- `frontend/src/libs/async-queue.ts`：异步任务队列工具，控制串行或节流执行。
- `frontend/src/libs/async.ts`：通用异步工具函数。
- `frontend/src/libs/editor-backend.ts`：前端访问后端 API 的适配层，同时维护素材 URL 与素材 ID 映射。
- `frontend/src/libs/evt.ts`：轻量事件总线。
- `frontend/src/libs/ffmpeg.ts`：浏览器端 FFmpeg 封装，负责加载 wasm、转码、抽音频、切片。
- `frontend/src/libs/file.ts`：文件相关工具，如 Blob/File/Base64 转换、下载、MD5。
- `frontend/src/libs/history-machine.ts`：历史状态机辅助工具。
- `frontend/src/libs/index.ts`：多媒体工具聚合导出。
- `frontend/src/libs/object.ts`：对象工具函数，如安全赋值、深层字段处理。
- `frontend/src/libs/performance.ts`：性能打点与耗时标记。
- `frontend/src/libs/timeline.ts`：时间线数学与结构处理工具。

#### 模块层 `modules/advanced-export/`

- `frontend/src/modules/advanced-export/index.vue`：高级导出模块入口。
- `frontend/src/modules/advanced-export/export-panel.vue`：高级导出设置面板。
- `frontend/src/modules/advanced-export/export-modal.vue`：高级导出弹窗。
- `frontend/src/modules/advanced-export/types/index.ts`：高级导出模块类型定义。

#### 模块层 `modules/animations/`

- `frontend/src/modules/animations/animation-manager.ts`：动画注册表与动画管理器。
- `frontend/src/modules/animations/base-animation.ts`：动画基类。
- `frontend/src/modules/animations/index.ts`：动画模块统一导出。
- `frontend/src/modules/animations/preset-animations.ts`：内置动画预设集合。

#### 模块层 `modules/filters/`

- `frontend/src/modules/filters/base-filter.ts`：滤镜基类。
- `frontend/src/modules/filters/css-filters.ts`：基于 CSS/Canvas 的滤镜定义。
- `frontend/src/modules/filters/filter-manager.ts`：滤镜管理器，负责注册与查找。
- `frontend/src/modules/filters/index.ts`：滤镜模块统一导出。

#### 模块层 `modules/transitions/`

- `frontend/src/modules/transitions/base-transition.ts`：转场基类。
- `frontend/src/modules/transitions/effects-transitions.ts`：内置转场效果实现集合。
- `frontend/src/modules/transitions/transition-manager.ts`：转场注册表与运行管理器。
- `frontend/src/modules/transitions/index.ts`：转场模块统一导出。

#### 类型层

- `frontend/src/types/index.ts`：前端全局类型中心，定义上下文、轨道、片段、素材、扩展接口等。

#### 组件层 `components/`

- `frontend/src/components/adjustable-box/index.vue`：可调节矩形框组件，用于拖拽与缩放。
- `frontend/src/components/audio-shape/index.vue`：音频波形展示组件。
- `frontend/src/components/context-menu/index.vue`：右键菜单组件。
- `frontend/src/components/draggable-handler/index.vue`：拖拽控制柄组件。
- `frontend/src/components/effect-icon/index.vue`：效果图标展示组件。
- `frontend/src/components/rotate-input/index.vue`：旋转输入组件。
- `frontend/src/components/scroll-box/index.ts`：滚动容器逻辑封装。
- `frontend/src/components/scroll-box/index.vue`：滚动容器组件。
- `frontend/src/components/sprite-image/index.vue`：精灵图组件。
- `frontend/src/components/sprite-image/transition-icon.vue`：转场图标精灵组件。
- `frontend/src/components/system-fonts/index.vue`：系统字体选择组件。
- `frontend/src/components/system-fonts/utils.ts`：系统字体枚举与工具函数。

#### 资源与样式

- `frontend/src/img/effect-icons.jpg`：效果图标图集。
- `frontend/src/img/rotate.svg`：旋转图标资源。
- `frontend/src/img/transition-sprite.jpg`：转场预览图集。
- `frontend/src/styles/export-button.less`：高级导出按钮样式。
- `frontend/src/styles/form.less`：表单通用样式。
- `frontend/src/styles/library.less`：素材库与列表通用样式。

#### 视图层 `views/editor/`

- `frontend/src/views/editor/index.vue`：编辑器主装配页，组合播放器、素材库、时间线、右侧面板。
- `frontend/src/views/editor/ai-preview-overlay.vue`：AI 预览遮罩层。

#### 视图层 `views/library/`

- `frontend/src/views/library/index.vue`：素材库主入口。
- `frontend/src/views/library/ai/index.vue`：AI 素材/AI 任务视图。
- `frontend/src/views/library/audio/index.vue`：音频素材库视图。
- `frontend/src/views/library/image/index.vue`：图片素材库视图。
- `frontend/src/views/library/text/index.vue`：文本素材库视图。
- `frontend/src/views/library/transition/index.vue`：转场素材库视图。
- `frontend/src/views/library/video/index.vue`：视频素材库视图。
- `frontend/src/views/library/_shared/aside.vue`：素材库左侧导航。
- `frontend/src/views/library/_shared/container.vue`：素材库通用容器。
- `frontend/src/views/library/_shared/import.vue`：文件导入、目录导入、转码入口。
- `frontend/src/views/library/_shared/list.vue`：素材列表、单个添加、批量添加、多选模式。

#### 视图层 `views/loading/`

- `frontend/src/views/loading/index.vue`：全局加载指示组件。

#### 视图层 `views/manager/`

- `frontend/src/views/manager/index.vue`：时间线管理器总入口。
- `frontend/src/views/manager/aside/index.vue`：轨道左侧信息区。
- `frontend/src/views/manager/container/index.vue`：时间线总容器。
- `frontend/src/views/manager/cursor/index.vue`：播放头/游标视图。
- `frontend/src/views/manager/main/index.vue`：时间线主体内容区。
- `frontend/src/views/manager/ruler/index.vue`：时间轴标尺。
- `frontend/src/views/manager/scaler/index.vue`：时间线缩放控制组件。
- `frontend/src/views/manager/ticker/index.vue`：刻度与滚动联动组件。
- `frontend/src/views/manager/tool-bar/index.vue`：时间线工具栏。
- `frontend/src/views/manager/segments/audio.vue`：音频片段渲染组件。
- `frontend/src/views/manager/segments/image.vue`：图片片段渲染组件。
- `frontend/src/views/manager/segments/text.vue`：文本片段渲染组件。
- `frontend/src/views/manager/segments/transition.vue`：转场片段渲染组件。
- `frontend/src/views/manager/segments/video.vue`：视频片段渲染组件。

#### 视图层 `views/panel/`

- `frontend/src/views/panel/index.vue`：右侧属性面板总入口。
- `frontend/src/views/panel/animation/index.vue`：动画属性面板。
- `frontend/src/views/panel/audio/index.vue`：音频属性面板。
- `frontend/src/views/panel/basic/index.vue`：基础属性面板。
- `frontend/src/views/panel/filter/index.vue`：滤镜属性面板。
- `frontend/src/views/panel/video/index.vue`：视频属性面板。
- `frontend/src/views/panel/text/index.vue`：文本属性面板。
- `frontend/src/views/panel/text/contenteditable.vue`：富文本可编辑输入组件。
- `frontend/src/views/panel/text/types.ts`：文本面板类型定义。

#### 视图层 `views/player/`

- `frontend/src/views/player/index.vue`：播放器总入口。
- `frontend/src/views/player/button.vue`：播放控制按钮。
- `frontend/src/views/player/container.vue`：播放器容器。
- `frontend/src/views/player/screen.vue`：播放器画面显示区域。

#### 视图层 `views/provider/`

- `frontend/src/views/provider/index.vue`：全局 Provider，挂载 naive-ui、主题、语言、消息组件等上下文。

#### 视图层 `views/reset-button/`

- `frontend/src/views/reset-button/index.vue`：重置项目与清理本地/后端数据的入口按钮。

#### 视图层 `views/select-aspect-ratio/`

- `frontend/src/views/select-aspect-ratio/index.vue`：画幅比例切换组件。

#### 视图层 `views/theme-box/`

- `frontend/src/views/theme-box/index.vue`：主题容器组件。

#### 视图层 `views/theme-switch/`

- `frontend/src/views/theme-switch/index.vue`：主题切换组件。

#### 视图层 `views/time-clock/`

- `frontend/src/views/time-clock/index.vue`：时间显示组件。

#### 视图层 `views/toast/`

- `frontend/src/views/toast/index.vue`：全局 Toast 视图。

#### 视图层 `views/tools/`

- `frontend/src/views/tools/clear/index.vue`：清空时间线工具。
- `frontend/src/views/tools/concat/index.vue`：拼接片段工具。
- `frontend/src/views/tools/delete/index.vue`：删除片段工具。
- `frontend/src/views/tools/flip-h/index.vue`：水平翻转工具。
- `frontend/src/views/tools/history-recover/index.vue`：历史恢复工具。
- `frontend/src/views/tools/redo/index.vue`：重做工具。
- `frontend/src/views/tools/split/index.vue`：分割工具。
- `frontend/src/views/tools/split-keep-left/index.vue`：分割后保留左段工具。
- `frontend/src/views/tools/split-keep-right/index.vue`：分割后保留右段工具。
- `frontend/src/views/tools/undo/index.vue`：撤销工具。

### 8.3 如何使用这份全量文件清单

- 想查前端某个按钮属于哪层：先看 `views/`。
- 想查时间线交互逻辑：重点看 `hooks/index.ts`、`hooks/manager.ts`、`views/manager/*`。
- 想查素材与后端同步：重点看 `libs/editor-backend.ts`、`hooks/library.ts`、`api/editor/projects.py`、`studio_service.py`。
- 想查导出：重点看 `modules/advanced-export/*`、`api/editor/exports.py`、`editor_export_service.py`、`advanced_render_service.py`。
- 想查 AI 剪辑：重点看 `views/library/ai/index.vue`、`api/editor/ai.py`、`video.py`、`editor_ai_orchestrator.py`。
