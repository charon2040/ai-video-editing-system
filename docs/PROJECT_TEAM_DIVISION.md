# AI 视频解说剪辑系统项目分工文档

## 1. 文档目的

本文档用于说明本项目三人协作时的职责边界、交付物、技术难度和验收标准。分工原则是：三个人都承担核心功能闭环，而不是简单拆成“后端、前端、文档”或“核心、页面、杂项”。

项目当前定位为本地运行的 AI 视频解说剪辑系统，核心流程为：

```text
上传视频 -> ASR 字幕识别 -> LLM 生成/拆分文案 -> 人工审核 -> TTS/上传配音 -> LLM 选片 -> FFmpeg 渲染 -> 下载结果
```

## 2. 分工原则

- 每个人都负责一条可独立验收的业务闭环。
- 每个人都包含后端逻辑、前端交互、联调验证和文档补充。
- 每个人都涉及核心功能，不设置纯文档岗或纯打包岗。
- 每个人负责的模块之间边界清楚，减少多人同时修改同一个文件。
- 不把模型权重、运行缓存、数据库、生成视频、私密 `.env` 纳入提交。

## 3. 总体分工

```text
成员 A：内容理解、知识注入与文案审核闭环
成员 B：配音、选片与成片渲染闭环
成员 C：项目工作台、任务编排与运行状态闭环
```

这三条闭环分别对应系统主流程中的三个核心阶段：

```text
A：原视频内容 -> 字幕 -> 文案草稿 -> 人工审核
B：确认文案 -> 配音时长 -> 语义选片 -> 成片输出
C：用户/项目 -> 任务创建 -> 工作流调度 -> 状态追踪 -> 资源访问
```

## 4. 成员 A：内容理解、知识注入与文案审核闭环

### 4.1 负责范围

成员 A 负责“视频内容转成可审核解说文案”的核心闭环。该成员需要保证用户上传素材后，系统可以基于 ASR 字幕、项目知识库和本次补充事实生成一版可修改、事实尽量可靠、按事件拆分的文案 beats。

主要代码范围：

```text
clip_mvp/app/services/asr_workflow_service.py
clip_mvp/app/services/draft_workflow_service.py
clip_mvp/app/services/task_draft_phase_service.py
clip_mvp/app/services/task_review_service.py
clip_mvp/app/services/llm_narration_service.py
clip_mvp/app/services/llm_draft_service.py
clip_mvp/app/services/llm_prompt_service.py
clip_mvp/app/services/llm_format_service.py
clip_mvp/app/services/llm_*_format_service.py
clip_mvp/app/services/project_knowledge_service.py 中上下文构建相关逻辑
clip_mvp/app/domain/schemas.py 中 DraftBeat、SubtitleUnit、TaskResult 文案相关字段
clip_mvp/frontend/src/components/DraftReviewPanel.vue
clip_mvp/frontend/src/components/KnowledgePanel.vue
clip_mvp/frontend/src/components/TaskCreateForm.vue 中需求、知识库、补充事实相关区域
clip_mvp/frontend/src/views/KnowledgeView.vue
```

### 4.2 具体任务

- 维护 ASR 字幕进入文案阶段的数据结构和缓存读取。
- 维护 AI 解说模式下的文案初稿生成逻辑。
- 维护定稿文案模式下的文案拆 beat 逻辑。
- 维护文案 prompt，确保全量字幕、本次补充事实和知识库进入 LLM。
- 维护 grounding 输出和事实依据校验。
- 维护本次补充事实优先级，避免长期知识库覆盖单次任务事实。
- 维护文案 JSON 解析、事实一致性校验、beat 原子性校验和 repair 流程。
- 保证用户确认后的 `draft_beats` 不被后端静默改写。
- 维护文案审核 UI，包括 beat 编辑、保存、确认和错误提示。
- 补充文案阶段自测记录，包括知识库、补充事实、事件拆分和文案审核。

### 4.3 技术难点

- LLM 输出不可控，需要用 prompt、schema、校验和 repair 降低事实漂移。
- 原始 ASR 字幕存在错字、断句和噪声，需要在不本地强行改写语义的前提下约束文案质量。
- 每个 beat 既要是完整解说文案，又要对应后续可剪的一段连续素材。
- 知识库是长期背景，本次补充事实是单次硬事实，两者优先级必须清晰。

### 4.4 交付物

- 上传视频后可生成 ASR 字幕。
- AI 解说模式可生成 `draft_script`、`draft_beats`、`grounding`、`suggestions`。
- 定稿文案模式可保留用户正文并拆分 beats。
- 文案审核页面可保存和确认草稿。
- 本次补充事实能进入任务 payload，并在 LLM 文案阶段作为准确信息依据。
- 文案阶段相关设计说明更新到需求和系统设计文档。

### 4.5 验收标准

```bat
cd /d F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app

cd /d F:\FUNASR\clip_mvp\frontend
npm run build
```

手工验收：

- 创建 AI 解说任务后，任务能进入 `waiting_review`。
- 草稿页面能展示并编辑 beats。
- 用户填写“本次补充事实”后，文案不应出现与补充事实相反的明确断言。
- 定稿文案模式下，系统不主动改写用户正文。

## 5. 成员 B：配音、选片与成片渲染闭环

### 5.1 负责范围

成员 B 负责“确认文案转成最终成片”的核心闭环。该成员需要保证用户确认文案后，系统可以生成或接收配音，获得每段配音时长，按语义和时长匹配原视频画面，并渲染输出可播放的短视频。

主要代码范围：

```text
clip_mvp/app/services/voice_workflow_service.py
clip_mvp/app/services/tts_service.py
clip_mvp/app/services/tts_*_service.py
clip_mvp/app/services/cosyvoice_runtime_service.py
clip_mvp/app/services/voice_profile_*_service.py
clip_mvp/app/services/voice_binding_service.py
clip_mvp/app/services/alignment_workflow_service.py
clip_mvp/app/services/alignment_*_service.py
clip_mvp/app/services/llm_alignment_service.py
clip_mvp/app/services/task_finalize_*_service.py
clip_mvp/app/services/render_workflow_service.py
clip_mvp/app/services/media_*_service.py
clip_mvp/app/api/routes/voice_profiles.py
clip_mvp/app/domain/schemas.py 中 SynthesizedBeat、AlignedSegment、AlignmentPlan 相关内容
clip_mvp/frontend/src/components/MatchedSegmentsPanel.vue
clip_mvp/frontend/src/components/ClipPlansPanel.vue
clip_mvp/frontend/src/components/TaskDetail.vue 中结果展示、播放和下载区域
clip_mvp/frontend/src/components/TaskCreateForm.vue 中配音参数相关区域
```

### 5.2 具体任务

- 维护 TTS 逐 beat 配音和真实时长读取。
- 维护上传完整配音模式和配音 ASR 切分。
- 维护配音模板创建、参考音频上传、音色选择和 TTS 速度参数。
- 维护 CosyVoice 本地服务启动、预热和调用。
- 维护 LLM 选片输入：reviewed beats、voice durations、全量 subtitles、project context。
- 维护 LLM 选片输出解析、数量校验、时长校验和错误提示。
- 维护 `matched_segments`、`selection_strategy`、`clip_plan` 保存。
- 维护 FFmpeg 剪切、拼接、旁白混音、SRT、EDL 输出。
- 维护结果预览、片段列表、下载链接和历史方案 UI。
- 补充 finalize 阶段自测记录，包括配音、选片、渲染和输出文件检查。

### 5.3 技术难点

- TTS 真实时长决定最终选片窗口，音频和视频不能错位。
- LLM 选片必须同时满足语义匹配、时间顺序和配音时长。
- FFmpeg 渲染需要处理原声保留、旁白混音、尾音补齐和输出文件生成。
- 上传完整配音时，配音 ASR 和文案 beat 对齐存在误差。
- CosyVoice 模型服务启动慢且依赖环境复杂，需要清晰的运行状态反馈。

### 5.4 交付物

- 用户确认文案后可生成 TTS 或使用上传配音。
- 系统可按配音时长完成 LLM 选片。
- 系统可生成 MP4、SRT、EDL。
- 任务详情页可展示最终选片、语义参考、输出时间轴和下载链接。
- 配音模板可创建、选择和用于任务。
- 成片阶段相关设计说明更新到需求和系统设计文档。

### 5.5 验收标准

```bat
cd /d F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app

cd /d F:\FUNASR\clip_mvp\frontend
npm run build
```

手工验收：

- 已确认文案的任务可以进入配音、选片、渲染。
- 输出视频可播放，旁白不被截断。
- matched segments 数量与 beats 一致。
- 前端能展示最终成片、SRT、EDL 和历史方案。
- 新建配音模板后能在任务创建表单中选择。

## 6. 成员 C：项目工作台、任务编排与运行状态闭环

### 6.1 负责范围

成员 C 负责“多用户项目化使用和任务运行管理”的核心闭环。该成员不是文档或杂项角色，而是负责用户如何进入系统、如何按项目组织任务、任务如何被创建和调度、状态如何被追踪、资源如何被安全访问。

主要代码范围：

```text
clip_mvp/app/api/routes/auth.py
clip_mvp/app/api/routes/system.py
clip_mvp/app/api/routes/tasks.py 中任务生命周期、查询、重生成和删除相关接口
clip_mvp/app/api/routes/protected_files.py
clip_mvp/app/api/task_form_normalizer.py
clip_mvp/app/core/
clip_mvp/app/repositories/
clip_mvp/app/services/auth_service.py
clip_mvp/app/services/project_service.py
clip_mvp/app/services/task_service.py
clip_mvp/app/services/task_lifecycle_service.py
clip_mvp/app/services/task_factory_service.py
clip_mvp/app/services/task_runner_service.py
clip_mvp/app/services/task_worker_service.py
clip_mvp/app/services/task_state_service.py
clip_mvp/app/services/task_event_service.py
clip_mvp/app/services/task_query_service.py
clip_mvp/app/services/task_bootstrap_service.py
clip_mvp/app/services/runtime_*_service.py
clip_mvp/app/services/protected_file_service.py
clip_mvp/app/workflows/
clip_mvp/frontend/src/router/
clip_mvp/frontend/src/views/DashboardView.vue
clip_mvp/frontend/src/views/LoginView.vue
clip_mvp/frontend/src/views/ProjectWorkspaceView.vue
clip_mvp/frontend/src/views/ProjectSettingsView.vue
clip_mvp/frontend/src/views/TasksView.vue
clip_mvp/frontend/src/views/RuntimeView.vue
clip_mvp/frontend/src/components/TaskEventTimeline.vue
clip_mvp/frontend/src/components/ReplanPanel.vue
clip_mvp/frontend/src/stores/
clip_mvp/frontend/src/api/client.ts
```

### 6.2 具体任务

- 维护用户注册、登录、退出和 session 鉴权。
- 维护用户级项目、任务、知识库、配音模板访问隔离。
- 维护项目工作台、项目设置和项目默认配置。
- 维护任务创建、重生成、删除、恢复和状态流转。
- 维护任务后台 worker、任务事件日志和任务运行阶段展示。
- 维护工作流模板注册、读取和默认模板策略。
- 维护任务创建表单参数归一化和项目默认值应用。
- 维护受保护文件访问，避免未登录或跨用户读取上传/输出资源。
- 维护 SQLite schema、repository、迁移和历史数据兼容。
- 维护 Runtime 页面和环境探测，支撑真实部署联调。
- 维护安装、启动、打包、项目计划、需求规格和系统设计文档。

### 6.3 技术难点

- 用户、项目、任务、知识库、文件之间存在多层访问控制，越权风险高。
- 长任务需要状态恢复、事件追踪、重生成和删除资源清理。
- 工作流模板要支持当前固定流程，同时为后续可组合流程预留扩展。
- SQLite 需要兼容旧数据，同时支持用户隔离和项目隔离。
- Runtime 状态要把复杂本地依赖转成前端可理解的信息。

### 6.4 交付物

- 用户可以注册登录并进入项目列表。
- 用户可以创建项目、进入项目工作台、配置项目默认参数。
- 任务可按项目创建、查询、重生成、删除。
- 任务事件日志可展示 ASR、写稿、配音、选片、渲染阶段。
- 用户不能访问其他用户的任务和文件。
- 工作流模板可通过 API 查询并用于项目默认配置。
- 数据库初始化、迁移和历史兼容稳定。
- 安装、启动、打包文档可被他人按步骤执行。

### 6.5 验收标准

```bat
cd /d F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app

cd /d F:\FUNASR\clip_mvp\frontend
npm run build
```

手工验收：

- 未登录访问业务页面会跳转登录页。
- 用户 A 无法访问用户 B 的任务和文件。
- 项目删除规则符合限制：默认项目不可删除，有任务的项目不可删除。
- 任务事件日志能展示各阶段状态。
- Runtime 页面能显示 LLM、ASR、TTS、FFmpeg 状态。

## 7. 工作量与难度平衡说明

| 成员 | 核心闭环 | 后端深度 | 前端深度 | AI/媒体难度 | 工程难度 |
| --- | --- | --- | --- | --- | --- |
| A | 内容理解到文案审核 | LLM 文案、ASR、grounding、校验 | 文案审核、知识库输入 | 高 | 中 |
| B | 配音选片到成片输出 | TTS、LLM 选片、FFmpeg、输出 | 结果预览、片段展示、配音配置 | 高 | 高 |
| C | 项目工作台到任务运行 | 鉴权、任务生命周期、DB、工作流 | 登录、项目、任务、事件日志 | 中 | 高 |

三个人都承担核心能力：

- A 解决“写什么”的问题。
- B 解决“剪哪里、怎么生成成片”的问题。
- C 解决“谁在什么项目里如何跑完整任务”的问题。

## 8. 协作提交建议

建议每人使用独立分支：

```text
feature/member-a-draft-review
feature/member-b-finalize-render
feature/member-c-workspace-runtime
```

推荐提交顺序：

1. 成员 C 先提交用户、项目、任务运行和工作流模板底座，保证系统能创建和追踪任务。
2. 成员 A 提交 ASR、知识注入、LLM 文案和审核闭环，保证任务能进入 `waiting_review`。
3. 成员 B 提交配音、选片、渲染和结果展示闭环，保证任务能从审核后到 `completed`。
4. 三人共同完成真实素材联调、问题修复和最终文档校对。

## 9. 不纳入提交的内容

```text
clip_mvp/.env
clip_mvp/data/*.db
clip_mvp/data/tmp/
clip_mvp/uploads/
clip_mvp/audio/
clip_mvp/outputs/
clip_mvp/frontend/node_modules/
clip_mvp/frontend/dist/
third_party/
*.log
*.zip
```

## 10. 最终联合验收

- 新用户可以注册登录。
- 用户可以创建项目和知识库。
- 用户可以上传视频创建 AI 解说任务。
- 系统可以生成文案初稿并进入人工审核。
- 用户确认文案后系统可以生成配音、匹配素材并渲染成片。
- 最终结果可预览和下载。
- 任务事件日志能展示主要阶段耗时和结果。
- 文档能说明项目目标、需求、设计、分工和部署方式。
