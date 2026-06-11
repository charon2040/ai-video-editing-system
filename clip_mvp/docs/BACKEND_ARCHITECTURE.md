# Clip MVP 后端工程化架构设计

## 1. 是否需要换后端框架

不建议现在换掉 FastAPI。

原因：

- 当前业务是文件上传、长任务编排、本地模型服务、状态轮询和静态资源服务，FastAPI 能覆盖这些需求。
- 现在的问题不是框架能力不足，而是代码层级不清、DTO 不稳定、数据库访问和业务编排耦合。
- 换成 Django、Flask 或其他框架，只会把当前的松散 dict、任务编排和持久化耦合搬过去。

正确方向是保留 FastAPI，补齐工程分层：

```text
API Routes
  -> Application Use Cases / Workflows
  -> Domain Models / DTO
  -> Repository Interfaces
  -> Infrastructure Implementations
```

## 2. 目标后端结构

建议演进成下面结构：

```text
app/
  api/
    routes/
      tasks.py
      runtime.py
      voice_profiles.py
      knowledge.py
    schemas/
      task_requests.py
      task_responses.py
      voice_profile_schemas.py
  application/
    task_orchestrator.py
    commands/
      create_task.py
      approve_draft.py
      replan_task.py
      delete_task.py
    workflows/
      asr_workflow.py
      draft_workflow.py
      voice_workflow.py
      alignment_workflow.py
      render_workflow.py
  domain/
    models/
      task.py
      draft.py
      alignment.py
      voice.py
      artifact.py
    services/
      duration_policy.py
      task_state_machine.py
  infrastructure/
    db/
      sqlite.py
      repositories/
        task_repository.py
        asr_cache_repository.py
        clip_plan_repository.py
        knowledge_repository.py
        voice_profile_repository.py
    providers/
      asr_funasr.py
      llm_openai_compatible.py
      tts_cosyvoice.py
      media_ffmpeg.py
  core/
    config.py
    logging.py
    errors.py
```

## 3. 当前已完成的中间态

当前已经从原来的单体 `task_service.py` 中拆出：

- `asr_workflow_service.py`
- `draft_workflow_service.py`
- `voice_workflow_service.py`
- `alignment_workflow_service.py`
- `render_workflow_service.py`

这是正确的第一步，但还只是 service 层拆分，不是最终工程结构。

下一步不是继续盲目拆文件，而是先固定数据契约。

## 4. DTO/schema 优先级

后端现在最大隐患是任务结果字段靠松散 dict 传递。必须先固定这些 DTO：

```python
class DraftBeat:
    id: str
    order: int
    title: str
    text: str
    voice_duration_ms: int

class VoiceBeat(DraftBeat):
    audio_path: str

class AlignedSegment:
    beat_id: str
    start_ms: int
    end_ms: int
    semantic_start_ms: int
    semantic_end_ms: int
    subtitle_text: str
    narration_text: str
    voice_duration_ms: int

class TaskResult:
    draft_script: str
    draft_beats: list[DraftBeat]
    matched_segments: list[AlignedSegment]
    selection_strategy: str
    actual_duration_ms: int
    voiceover_duration_ms: int
```

落地顺序：

1. 在 `app/domain/models/` 建 Pydantic v2 models。
2. Workflow 入参和返回值改成 model，不再直接返回 dict。
3. API response 再序列化成 dict。
4. 前端只依赖 response schema，不再猜字段。

## 5. Repository 拆分

`app/core/db.py` 现在承担了 schema 初始化、迁移和所有表访问。后续应该拆成 repository：

- `TaskRepository`
- `TaskEventRepository`
- `ASRCacheRepository`
- `ClipPlanRepository`
- `KnowledgeRepository`
- `VoiceProfileRepository`

短期不需要换 SQLite。SQLite 对本地单机 MVP 足够，真正要换的是访问边界。

未来如果要多用户或并发任务，再切 PostgreSQL。

## 6. 任务队列

现在任务用线程启动，能跑 MVP，但不是正式工程的最终形态。

建议演进：

- 短期：保留线程，但把 worker 抽成 `TaskWorker`，集中管理 active task、恢复、取消。
- 中期：引入 `APScheduler` 或 `arq` 这类轻量队列。
- 长期：如果要多机器，使用 Redis Queue/Celery。

当前不建议马上上 Celery。它会增加 Redis、worker 进程、部署复杂度，主链路还没完全稳定时收益不高。

## 7. Provider 抽象

Provider 要晚于 DTO，不要过早抽象。

目标接口：

```python
class ASRProvider:
    def transcribe(audio_path: Path) -> list[SubtitleUnit]: ...

class LLMProvider:
    def generate_draft(...) -> DraftResult: ...
    def align_beats(...) -> list[AlignedSegment]: ...

class TTSProvider:
    def synthesize(text: str, voice: str, mode: str) -> VoiceOutput: ...

class MediaProvider:
    def cut_and_concat(...) -> Path: ...
```

目前可以先保留：

- FunASRProvider
- OpenAICompatibleLLMProvider
- CosyVoiceProvider
- FFmpegProvider

## 8. API 层规范

API route 不应该再做大量业务参数处理。

目标：

- Request schema 放 `app/api/schemas/`。
- Route 只负责接收请求、调用 command/usecase、转换异常。
- 业务判断放 application 层。
- 领域校验放 domain 层。

例如：

```text
POST /api/tasks
  -> CreateTaskRequest
  -> CreateTaskCommand
  -> TaskOrchestrator.create_task()
```

## 9. 错误处理

当前很多错误直接 `RuntimeError` 文案抛出。建议建立错误类型：

- `TaskNotFound`
- `InvalidTaskState`
- `ASRFailed`
- `DraftGenerationFailed`
- `VoiceSynthesisFailed`
- `AlignmentFailed`
- `RenderFailed`

API 层统一映射 HTTP code。

## 10. 下一步落地顺序

推荐顺序：

1. 建 `domain/models`，固定 `DraftBeat / VoiceBeat / AlignedSegment / TaskResult`。
2. 改 `alignment_workflow_service.py` 和 `render_workflow_service.py` 用 DTO。
3. 拆 `app/core/db.py` repository。
4. 抽 `TaskWorker`，把线程和任务恢复从 `task_service.py` 移出去。
5. API route 改用 request/response schema。
6. 最后再做 Provider 抽象。

不建议现在做：

- 直接换 Django。
- 直接上 Celery。
- 直接加复杂权限/用户系统。
- 直接把视觉理解塞进现有 result dict。

当前目标应该是：先让工程结构稳定，再扩展画面理解、多工作流模板和多模型 Provider。

