# Clip MVP 前后端重构执行文档

## 1. 当前结论

当前项目核心链路已经能跑通，但代码结构仍然偏临时集成，主要问题不是某个模型或某个 prompt，而是职责边界不清。

目标主链路必须保持为：

```text
raw_subtitles -> draft_beats -> review -> tts -> raw_subtitles + beats + voice_duration -> final segments -> render
```

重构原则：

- 不让本地关键词、贪心匹配、静默合并接管语义判断。
- LLM 负责语义，后端负责合法化、校验、持久化和渲染。
- 用户确认过的文案结构不能被后端静默改写。
- 每次拆分只移动职责，不改变业务输出。
- 前端先保持无构建静态脚本模式，避免现在引入 Vite/React 造成新变量。

## 2. 当前代码审查

### 2.1 后端现状

主要文件体量：

- `app/services/task_service.py`：约 1560 行，任务 CRUD、知识库、文案草稿、ASR、TTS、LLM 对齐、渲染都在同一个类里。
- `app/services/llm_service.py`：约 760 行，草稿 prompt、grounding、最终 beat 对齐、响应归一化混在一起。
- `app/services/tts_service.py`：约 610 行，CosyVoice 调用、拆句、音频速度处理、服务探测耦合较重。
- `app/core/db.py`：约 700 行，表结构、迁移、所有 repository 操作集中在一个文件。

当前 `TaskService._run_task()` 是最大风险点。它同时负责：

- 解析 task payload。
- 复用或生成 ASR。
- 生成 draft。
- 等待 review 后继续。
- 调用 TTS 生成逐 beat 音频。
- 调用 LLM 做最终选片。
- 校验时长。
- 保存 clip plan。
- 调用 FFmpeg 渲染。
- 拼接配音并混流。
- 更新任务状态和事件。

这会导致两个直接问题：

- 任何一段逻辑出问题时，定位困难，例如“卡在 58%”或“卡在 86%”只能看大函数日志。
- 后续接视觉理解、更多 TTS 参数或工作流模板时，会继续往 `_run_task()` 里堆代码。

### 2.2 前端现状

主要文件体量：

- `static/app.js`：约 1800 行，表单、任务轮询、任务详情、历史记录、配音模板、知识库、事件日志都在一个文件。
- `static/index.html`：仍然是单页静态入口，DOM 区块较多。
- `static/runtime-panel.js` 已经抽出运行状态面板，是正确方向。
- `static/app.css`：约 980 行，页面布局和所有组件样式混在一起。

当前最大前端风险：

- `renderTaskDetail()` 过大，任务结果、草稿编辑、选片展示、事件展示、按钮逻辑混在一起。
- `renderTaskHistory()` 过大，历史卡片、删除、状态摘要和结果摘要耦合。
- 全局变量很多，新增功能容易影响其他模块。

### 2.3 数据结构现状

任务结果大量使用松散 dict：

- `draft_script`
- `draft_beats`
- `grounding`
- `matched_segments`
- `selection_strategy`
- `voiceover_script`
- `voiceover_duration_ms`
- `actual_duration_ms`
- `clip_plan_id`

这些字段现在可以工作，但缺少正式 DTO/schema，所以前后端都在猜字段是否存在、类型是否稳定。后续接画面理解时，如果没有先固定 `DraftBeat`、`VoiceBeat`、`AlignedSegment`、`TaskResult`，会继续混乱。

## 3. 目标后端架构

目标结构：

```text
app/
  api/routes/
    tasks.py
    system.py
    voice_profiles.py
  core/
    config.py
    db.py
  domain/
    schemas.py
    task_models.py
  services/
    task_service.py
    asr_workflow_service.py
    draft_workflow_service.py
    voice_workflow_service.py
    alignment_workflow_service.py
    render_workflow_service.py
    llm_service.py
    tts_service.py
    media_service.py
```

### 3.1 `task_service.py`

保留为任务编排器，只做：

- 创建任务。
- 更新任务状态。
- 调用各 workflow。
- 持久化任务结果。
- 处理异常和任务恢复。

不再直接写 ASR、TTS、对齐、渲染细节。

### 3.2 `asr_workflow_service.py`

职责：

- 根据 source hash 查 ASR 缓存。
- 抽取音频。
- 调用 FunASR。
- 写入 ASR 缓存。
- 通过回调更新任务状态和事件。

它不理解文案、配音、选片。

### 3.3 `draft_workflow_service.py`

职责：

- 输入 `raw_subtitles + request + style + project_context`。
- 调用 LLM 生成 `draft_script + draft_beats + grounding`。
- 标准化 draft beats。

它不做 TTS，也不做最终选片。

### 3.4 `voice_workflow_service.py`

职责：

- 输入用户确认的 beats。
- 调用 TTS 逐段生成音频。
- 读取每段真实 `voice_duration_ms`。
- 管理 TTS 缓存。

它只生成声音和时长，不决定画面。

### 3.5 `alignment_workflow_service.py`

职责：

- 输入 `raw_subtitles + reviewed_beats + voice_duration_ms`。
- 调用 LLM 做全量 beat 对齐。
- 标准化并校验 `AlignedSegment`。
- 返回 `selection_strategy`。

它不裁视频，也不混音。

### 3.6 `render_workflow_service.py`

职责：

- 输入最终 segments。
- 调用 FFmpeg 剪辑、拼接、生成 srt/edl。
- 如果有配音，拼接 voiceover 并 mux。
- 输出 artifacts。

它不调用 LLM/TTS。

## 4. 目标前端架构

前端暂时继续使用静态 JS，不引入打包工具。目标是把 `app.js` 拆成面板级模块。

```text
static/
  index.html
  app.js
  api-client.js
  formatters.js
  runtime-panel.js
  task-detail-panel.js
  task-history-panel.js
  voice-profile-panel.js
  knowledge-panel.js
  app.css
```

### 4.1 `app.js`

只保留：

- DOM 初始化。
- 全局状态。
- 表单提交。
- 轮询控制。
- 调用各 panel render 函数。

### 4.2 `api-client.js`

封装：

- `request()`
- `fetchTask()`
- `fetchHistory()`
- `fetchRuntimeStatus()`
- `fetchVoiceProfiles()`
- `fetchProjectKnowledge()`
- `saveProjectKnowledge()`

### 4.3 `task-detail-panel.js`

负责：

- 当前任务状态。
- draft review UI。
- matched segments 展示。
- task events 展示。
- 下载链接。

这是前端第一优先级拆分点。

### 4.4 `task-history-panel.js`

负责：

- 历史任务列表。
- 删除任务。
- 清理已完成任务。
- 历史 clip plan 简要展示。

### 4.5 `voice-profile-panel.js`

负责：

- 标准配音模板。
- 克隆配音模板。
- 折叠/展开。
- 上传参考音频。

### 4.6 `knowledge-panel.js`

负责：

- 知识库切换。
- 新建知识库。
- 编辑知识库内容。
- 保存状态。

## 5. DTO/schema 设计

后续应在 `app/domain/task_models.py` 固定这些模型。

```python
class DraftBeat:
    id: str
    order: int
    title: str
    text: str
    voice_duration_ms: int = 0

class VoiceBeat(DraftBeat):
    audio_path: str
    voice_duration_ms: int

class AlignedSegment:
    beat_id: str
    title: str
    text: str
    start: int
    end: int
    semantic_start: int
    semantic_end: int
    content: str
    voice_duration_ms: int

class TaskResult:
    draft_script: str
    draft_beats: list[DraftBeat]
    matched_segments: list[AlignedSegment]
    selection_strategy: str
    voiceover_enabled: bool
    voiceover_duration_ms: int
    actual_duration_ms: int
```

迁移方式：

- 第一阶段继续输出 dict，内部先用 helper 标准化。
- 第二阶段引入 dataclass 或 Pydantic model。
- 第三阶段前端按稳定字段渲染，不再到处做字段兜底。

## 6. 分阶段执行计划

### Phase 1：低风险后端拆分

目标：不改变输出，只搬职责。

- 抽离 ASR 工作流。
- 抽离 TTS/voice 工作流。
- 抽离 alignment 工作流。
- 抽离 render 工作流。

验收：

- Python 编译通过。
- `/api/health` 通过。
- `/api/runtime` 通过。
- 用已有任务继续执行不报错。

### Phase 2：前端面板拆分

目标：降低 `app.js` 复杂度，不改变 UI。

- 抽 `task-detail-panel.js`。
- 抽 `task-history-panel.js`。
- 抽 `knowledge-panel.js`。
- 抽 `voice-profile-panel.js`。

验收：

- `node --check` 所有 JS 通过。
- 创建任务、草稿确认、删除任务、知识库切换可用。

### Phase 3：DTO/schema 固化

目标：让前后端字段稳定。

- 建 `DraftBeat`、`VoiceBeat`、`AlignedSegment`、`TaskResult`。
- API 返回稳定 shape。
- 前端按 DTO 渲染。

验收：

- 老任务详情仍能打开。
- 新任务 result 字段完整。
- 前端不再依赖过多 `|| {}` 和临时字段名。

### Phase 4：画面理解接入

目标：解决“字幕语义对了，但画面不是 BP 界面/不是关键画面”的问题。

建议路径：

- 先抽关键帧。
- 给字幕窗口挂轻量视觉标签。
- 最终对齐输入变成 `subtitle window + visual tags + beat + voice_duration`。
- LLM 不只判断字幕，还判断画面类型。

不要现在直接把视觉模块塞进 `task_service.py`，否则会扩大当前混乱。

### Phase 5：Provider 和 workflow 模板

目标：提高通用性。

- `ASRProvider`
- `LLMProvider`
- `TTSProvider`
- `narration_clip`
- `highlight_clip`
- `review_clip`

这一阶段放后面，因为现在 ASR/LLM/TTS 已经能跑，过早抽象会增加成本。

## 7. 近期优先级

当前最值得立刻做的顺序：

1. 抽 `asr_workflow_service.py`。
2. 抽 `voice_workflow_service.py`。
3. 抽 `alignment_workflow_service.py`。
4. 抽 `render_workflow_service.py`。
5. 抽 `task-detail-panel.js`。
6. 建 `task_models.py`。

不建议现在做：

- 立刻换前端框架。
- 立刻加视觉理解。
- 立刻做多 Provider 大抽象。
- 继续加入新的 TTS 模型。

原因是主流程已经能跑，当前瓶颈是代码边界，而不是再堆新能力。

## 8. 本轮执行状态

本轮已经完成第一阶段的大部分低风险拆分，主链路行为保持不变。

后端已拆出：

- `app/services/asr_workflow_service.py`：负责 ASR 缓存、音频抽取、FunASR 识别、ASR 缓存写入。
- `app/services/draft_workflow_service.py`：负责 LLM 文案初稿生成和 draft beats 标准化。
- `app/services/voice_workflow_service.py`：负责逐 beat TTS、TTS 缓存、真实配音时长探测。
- `app/services/alignment_workflow_service.py`：负责全局 LLM beat 对齐、片段标准化、配音时长校验。
- `app/services/render_workflow_service.py`：负责 FFmpeg 粗剪、配音轨拼接、混音、SRT/EDL 导出。

后端变化结果：

- `task_service.py` 从约 1560 行降到约 1010 行。
- `_run_task()` 仍然偏长，但已经从“所有细节都在一个函数里”变成“任务编排器调用多个 workflow”。
- 当前没有改变 LLM prompt、TTS 参数、选片策略或渲染策略。

前端已拆出：

- `static/formatters.js`：通用格式化、HTML 转义、状态标签、时长显示。
- `static/api-client.js`：基础 API 请求和错误解析。
- `static/runtime-panel.js`：运行环境状态面板，之前已完成。
- `static/task-detail-panel.js`：已先抽出方案历史和任务事件时间线两个纯渲染块。

前端变化结果：

- `static/app.js` 从约 1845 行降到约 1630 行。
- 当前仍保留静态脚本架构，没有引入构建工具。
- `renderTaskDetail()` 仍然是最大前端函数，下一步应继续拆。

下一步建议：

1. 继续拆 `renderTaskDetail()`：把 draft review、matched segments、knowledge snapshot、task actions 分别抽到 `task-detail-panel.js`。
2. 再拆 `renderTaskHistory()` 到 `task-history-panel.js`。
3. 后端下一步不是继续搬函数，而是建立正式 DTO/schema，让 workflow 之间不再传松散 dict。
4. 等 DTO 稳定后，再接画面理解，否则视觉标签会继续混进松散 result 字段里。

## 9. 验证清单

每次拆分后至少执行：

```powershell
E:\anaconda\envs\funasr-env\python.exe -m py_compile app\services\task_service.py
E:\anaconda\envs\funasr-env\python.exe -m py_compile app\services\<new_file>.py
node --check static\app.js
Invoke-RestMethod -Uri http://127.0.0.1:8010/api/health -Method Get
Invoke-RestMethod -Uri http://127.0.0.1:8010/api/runtime -Method Get
```

如果改了 TTS：

```powershell
E:\anaconda\envs\funasr-env\python.exe -c "from pathlib import Path; from app.services.tts_service import tts_service; p=Path(r'F:\FUNASR\clip_mvp\data\tmp\cosyvoice_refactor_smoke.wav'); out=tts_service.synthesize_to_file(text='这是重构后的配音测试。', voice='zh_female_default', output_path=p, voice_mode='standard', speed=1.0); print(out); print(p.exists())"
```

如果改了最终选片：

- 检查 `selection_strategy` 是否为 `global_llm_align` 或 `none`。
- 检查 `matched_segments` 数量是否等于 `draft_beats` 数量。
- 检查每段 `end - start` 是否贴近对应 `voice_duration_ms`。
- 检查最终视频时长是否接近配音总时长。
