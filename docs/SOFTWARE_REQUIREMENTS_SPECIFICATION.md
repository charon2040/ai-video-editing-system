# AI 视频解说剪辑系统软件需求规格说明书

## 1. 引言

### 1.1 编写目的

本文档描述 AI 视频解说剪辑系统的软件需求，包括系统目标、用户角色、功能需求、非功能需求、接口需求、数据需求和验收标准。本文档面向项目开发人员、测试人员、评审人员和后续维护人员。

### 1.2 项目背景

本系统用于将长视频自动加工为带解说文案、配音和剪辑画面的短视频。系统通过 ASR 获取原视频字幕，通过 LLM 生成或拆分文案，通过 TTS 或上传配音获得旁白时长，再通过 LLM 结合全量字幕和配音时长选择画面片段，最后通过 FFmpeg 渲染输出。

### 1.3 术语定义

| 术语 | 定义 |
| --- | --- |
| ASR | Automatic Speech Recognition，自动语音识别 |
| LLM | Large Language Model，大语言模型 |
| TTS | Text To Speech，文本转语音 |
| Beat | 一段可独立配音、审核和选片的文案段落 |
| Grounding | LLM 输出的事实依据说明 |
| Project Context | 项目知识库和本次补充事实合并后的上下文 |
| 本次补充事实 | 用户针对单次视频输入的硬事实，如左右方、队伍映射 |
| Knowledge Base | 项目级长期知识库，如人物、队伍、术语背景 |
| Matched Segment | 与某个 beat 对应的原视频时间片段 |
| EDL | Edit Decision List，剪辑决策列表 |

### 1.4 参考资料

- 当前项目代码：`F:\FUNASR\clip_mvp`
- 软件需求说明书编写规范
- 详细设计说明书编写规范
- FastAPI、Vue、FunASR、CosyVoice、FFmpeg 相关文档

## 2. 总体描述

### 2.1 产品定位

系统定位为本地运行的 AI 视频解说剪辑工具，面向需要快速从长视频生成解说短视频的用户。系统不是完整非线性编辑器，而是字幕和文案驱动的半自动剪辑系统。

### 2.2 产品功能概述

系统主要功能包括：

- 用户认证。
- 项目工作台。
- 项目知识库。
- 视频任务创建。
- ASR 字幕识别。
- LLM 文案生成。
- 人工文案审核。
- TTS 配音或上传配音。
- LLM 画面选片。
- FFmpeg 渲染输出。
- 任务事件日志。
- 运行环境检查。
- 配音模板管理。

### 2.3 用户角色

| 角色 | 说明 |
| --- | --- |
| 普通用户 | 注册登录后创建项目、管理知识库、上传视频并生成成片 |
| 项目维护者 | 配置本地环境、模型路径、LLM Key、TTS 服务 |
| 开发人员 | 维护工作流、服务、前端页面和部署文档 |

当前系统未实现管理员后台和角色权限分级，所有登录用户拥有自己的数据空间。

### 2.4 运行环境

客户端：

- Windows 桌面浏览器。
- 推荐 Chrome 或 Edge。

服务端：

- Windows 本地环境。
- Python 3.10+。
- Node.js 用于前端构建。
- FFmpeg / ffprobe。
- FunASR 模型。
- CosyVoice 模型和本地服务。
- OpenAI-compatible LLM API。

### 2.5 约束条件

- 当前为本地单机应用，不保证多机器并发。
- LLM API Key 由用户自行配置。
- 模型权重不应提交到代码仓库。
- 视频文件、生成音频、输出视频会占用较大磁盘空间。
- LLM 输出存在不确定性，需要人工审核文案。

## 3. 功能需求

### 3.1 用户认证

#### 3.1.1 注册

系统应支持用户输入用户名、密码和显示名完成注册。

约束：

- 用户名长度 3-32。
- 用户名只能包含字母、数字、下划线、点和短横线。
- 密码长度 6-128。
- 用户名不可重复。

#### 3.1.2 登录

系统应支持用户使用用户名和密码登录。登录成功后系统设置会话 Cookie。

#### 3.1.3 退出

系统应支持用户退出登录，并清除会话 Cookie。

#### 3.1.4 会话校验

系统应在访问业务接口时校验当前用户会话。未登录用户访问业务页面时应跳转到登录页。

### 3.2 项目管理

#### 3.2.1 项目列表

系统应展示当前用户拥有的项目列表。

#### 3.2.2 创建项目

系统应支持用户创建项目，项目字段包括标题、描述、默认知识库、默认工作流、默认时长、默认风格、默认配音参数。

#### 3.2.3 更新项目

系统应支持修改项目默认配置。

#### 3.2.4 删除项目

系统应支持删除非默认项目。若项目下仍有任务，系统应拒绝删除。

### 3.3 知识库管理

#### 3.3.1 创建知识库

系统应支持在项目下创建知识库。

#### 3.3.2 更新知识库

系统应支持修改知识库标题和内容。

#### 3.3.3 删除知识库

系统应支持删除项目知识库。若删除的是项目默认知识库，系统应按策略替换或清空默认绑定。

#### 3.3.4 知识库使用策略

任务创建时应支持：

- 不使用知识库。
- 使用项目默认知识库。
- 指定某个知识库。

#### 3.3.5 本次补充事实

系统应支持用户填写本次任务特有事实。此类事实用于本次视频，不写入长期知识库。若本次补充事实与长期知识库冲突，应以本次补充事实为准。

### 3.4 任务创建

#### 3.4.1 上传视频

系统应支持上传原始视频文件，并保存到本地上传目录。

#### 3.4.2 填写目标

系统应支持用户填写：

- 新的目标/要求。
- 定稿文案。
- 本次补充事实。
- 目标时长。
- 文案风格。
- 知识库策略。
- 配音模式。
- TTS 语速。
- 是否保留原视频声音。

#### 3.4.3 工作流选择

系统应支持至少两种工作流：

- `narration_clip`：AI 解说剪辑。
- `script_match_clip`：定稿文案匹配。

### 3.5 ASR 字幕识别

系统应从视频中抽取音频，并使用 FunASR 生成按时间顺序排列的字幕单元。

系统应基于源文件 hash 使用 ASR 缓存，避免重复识别同一视频。

### 3.6 文案初稿生成

#### 3.6.1 AI 解说模式

系统应将用户要求、项目上下文、目标时长和全量字幕传给 LLM，生成：

- `draft_script`
- `draft_beats`
- `grounding`
- `suggestions`

#### 3.6.2 定稿文案模式

若用户提供定稿文案，系统应只拆分文案为 beats，不主动改写正文。

#### 3.6.3 文案要求

每个 beat 应尽量对应一个连续事件或连续解说窗口，便于后续选片。系统应避免把多个不连续事件揉成一个 beat。

### 3.7 文案审核

系统应在生成文案后进入 `waiting_review` 状态。用户可修改：

- 整体文案。
- beat 标题。
- beat 正文。
- beat 顺序。

用户确认后系统进入配音和选片阶段。

### 3.8 配音处理

#### 3.8.1 TTS 配音

系统应支持按确认后的 beats 逐段生成配音音频，并记录每段真实配音时长。

#### 3.8.2 上传完整配音

系统应支持用户上传完整配音音频，并通过配音 ASR 与 beats 对齐，切分出每段配音时间。

#### 3.8.3 配音模板

系统应支持配音模板列表、创建和查看。克隆配音模板应关联参考音频。

### 3.9 画面匹配

系统应把确认后的 beats、全量原字幕、配音时长和项目上下文传给 LLM，由 LLM 为每段选择原视频时间范围。

要求：

- 返回条数应与 beats 数一致。
- 每段 final 范围应与对应配音时长接近。
- 选片应按时间顺序推进。
- 若 beat 是过程总结，应优先匹配真实过程画面，不优先选择赛后总结口播。
- 后端不应在 LLM 选片后静默扩窗或自动合并用户确认的 beats。

### 3.10 渲染输出

系统应使用 FFmpeg 按 matched segments 剪切并拼接视频，并混入配音或保留原声。

系统应输出：

- MP4 视频。
- SRT 字幕。
- EDL 文件。
- 任务结果元数据。

### 3.11 任务管理

系统应支持：

- 查看任务列表。
- 查看任务详情。
- 查看任务事件日志。
- 重生成方案。
- 删除任务。
- 清理已完成任务。
- 查看历史 clip plans。

删除任务时应清理该任务产生的输出资源，但不应误删可复用 ASR 缓存和其他任务引用的原视频。

### 3.12 运行时状态

系统应提供运行时状态页面，展示：

- 后端状态。
- ASR 依赖状态。
- LLM 配置状态。
- TTS/CosyVoice 状态。
- FFmpeg 状态。

## 4. 外部接口需求

### 4.1 用户界面

前端页面包括：

- 登录页。
- 项目列表页。
- 项目工作台。
- 项目设置页。
- 创建任务页。
- 任务列表页。
- 任务详情页。
- 知识库页。
- 运行时页。

### 4.2 后端 API

主要 API 包括：

```text
GET  /api/auth/me
POST /api/auth/login
POST /api/auth/register
POST /api/auth/logout

GET    /api/projects
POST   /api/projects
PUT    /api/projects/{project_id}
DELETE /api/projects/{project_id}

GET    /api/project-knowledge
POST   /api/project-knowledge
PUT    /api/project-knowledge/{knowledge_base_id}
DELETE /api/project-knowledge/{knowledge_base_id}

GET    /api/tasks
POST   /api/tasks
GET    /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
GET    /api/tasks/{task_id}/events
POST   /api/tasks/{task_id}/draft
POST   /api/tasks/{task_id}/approve-draft
POST   /api/tasks/{task_id}/replan

GET  /api/runtime
GET  /api/workflow-templates

GET  /api/voice-profiles
POST /api/voice-profiles
GET  /api/voice-profiles/{profile_id}
```

### 4.3 第三方接口

- OpenAI-compatible LLM API：用于文案生成和选片。
- CosyVoice HTTP 服务：用于 TTS 合成。
- FunASR：本地 ASR 推理。
- FFmpeg / ffprobe：音视频处理。

## 5. 数据需求

系统使用 SQLite 存储结构化数据。主要数据表：

| 表名 | 用途 |
| --- | --- |
| users | 用户账户 |
| user_sessions | 用户会话 |
| projects | 项目和默认配置 |
| project_knowledge | 项目知识库 |
| tasks | 任务主记录 |
| task_events | 任务阶段事件 |
| asr_cache | ASR 缓存 |
| clip_plans | 历史方案 |
| voice_profiles | 配音模板 |

主要文件目录：

| 目录 | 用途 |
| --- | --- |
| uploads | 上传原视频 |
| audio | 抽取音频 |
| outputs | 输出视频、字幕、EDL、配音 |
| data | SQLite、运行缓存、临时文件 |
| frontend/dist | 前端构建产物 |

## 6. 非功能需求

### 6.1 易用性

- 用户应能通过浏览器完成全流程操作。
- 长任务应展示阶段消息和事件日志。
- 文案必须可编辑确认后再进入最终处理。

### 6.2 可靠性

- 后端启动时应恢复中断任务到可重试状态。
- LLM 返回格式错误时应给出明确错误。
- 任务失败应保留错误信息，便于重新生成。

### 6.3 性能

- 相同视频应复用 ASR 缓存。
- TTS 应支持缓存和常驻 CosyVoice 服务。
- 任务运行应避免无意义轮询日志刷屏。

### 6.4 安全性

- 未登录用户不能访问业务接口。
- 文件访问接口需要鉴权。
- 用户只能访问自己的任务、知识库、项目和配音模板。
- `.env` 不得提交或分发真实密钥。

### 6.5 可维护性

- 后端按 API、services、repositories、domain、workflows 分层。
- 前端按 views、components、stores、api、router 分层。
- 工作流模板使用 JSON 描述，便于后续扩展。

### 6.6 可移植性

- 当前优先支持 Windows 本地环境。
- 模型目录和工具路径应通过 `.env` 配置覆盖。

## 7. 验收标准

### 7.1 基础验收

- 用户能注册并登录。
- 用户能创建项目和知识库。
- 用户能上传视频创建任务。
- 系统能生成文案并等待审核。
- 用户确认文案后系统能生成成片。
- 输出文件可预览和下载。

### 7.2 工程验收

```bat
cd /d F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app
E:\anaconda\envs\funasr-env\python.exe -c "from app.main import app; print('APP_IMPORT_OK', bool(app))"

cd /d F:\FUNASR\clip_mvp\frontend
npm run build
```

### 7.3 文档验收

项目应包含项目计划书、需求规格说明书、系统设计文档和三人分工文档。
