# Git 提交流程傻瓜版 SOP

本文档用于团队把本地 `clip_mvp` 项目提交到远程仓库时复用。目标是避免三类问题：

- 直接 `git add -A` 把旧代码删除、压缩包、模型、数据库、上传视频一起提交。
- 后提交的人覆盖相同文件，GitHub 显示 `0 changes`。
- `.gitignore` 误伤 `clip_mvp/app/main.py`、工作流模板等关键文件，导致远端代码拉下来不能跑。

## 0. 固定规则

所有人先遵守这 5 条：

```text
1. 不直接推 main。
2. 不使用 git add -A。
3. 不提交 .env、数据库、上传视频、输出视频、日志、zip、third_party。
4. 每个人只提交自己负责的业务范围。
5. 提交前必须看 git diff --cached --stat，确认暂存区内容正确。
```

所有命令默认在 PowerShell 执行。

```powershell
cd F:\FUNASR
$git = 'D:\软工实训\Git\cmd\git.exe'
```

## 1. 开始前检查

先确认远端和当前状态：

```powershell
& $git fetch origin main
& $git status --short --branch
& $git log --oneline --decorate --max-count=8
```

如果看到大量这种内容，不要直接提交：

```text
D backend/...
D frontend/...
D old version/...
?? clip_mvp/
?? third_party/
?? clip_mvp (2).zip
?? 备用/
```

这说明当前工作区是“旧代码删除 + 新项目未跟踪 + 无关文件混杂”的状态，必须按下面流程分批提交。

## 2. 建集成分支

由一个人负责建集成分支：

```powershell
& $git switch -c feature/clip-mvp-integration origin/main
```

如果分支已经存在：

```powershell
& $git switch feature/clip-mvp-integration
```

以后所有人都在这个分支上按顺序提交。最后只推这个分支。

## 3. 第一个提交：仓库清理

先修 `.gitignore`。不要保留这种裸规则：

```text
main.py
run.py
README.md
templates/
```

这些规则会误伤：

```text
clip_mvp/app/main.py
clip_mvp/run.py
clip_mvp/README.md
clip_mvp/app/workflows/templates/*.json
```

推荐保留或新增这些忽略项：

```text
.env
*.log
*.zip
third_party/
备用/

clip_mvp/.env
clip_mvp/data/
clip_mvp/uploads/
clip_mvp/audio/
clip_mvp/outputs/
clip_mvp/frontend/node_modules/
clip_mvp/frontend/dist/
__pycache__/
*.py[cod]
```

检查关键文件没有被忽略：

```powershell
& $git check-ignore -v clip_mvp/app/main.py clip_mvp/app/workflows/templates/narration_clip.json clip_mvp/app/workflows/templates/script_match_clip.json clip_mvp/requirements.txt
```

正常情况：没有任何输出。

然后只提交仓库清理、文档和脚本：

```powershell
& $git add .gitignore clip_mvp/.gitignore clip_mvp/.env.example clip_mvp/requirements.txt clip_mvp/docs clip_mvp/scripts
& $git diff --cached --stat
& $git status --short
```

确认没有 `.env`、`.db`、`uploads`、`outputs`、`third_party`、`*.zip` 后提交：

```powershell
& $git commit -m "chore(repo): prepare clip_mvp repository layout"
```

## 4. 第二个提交：成员 C 项目底座

成员 C 先提交项目工作台、任务、登录、运行状态、数据库、工作流入口。

建议暂存：

```powershell
& $git add clip_mvp/app/main.py
& $git add clip_mvp/app/api/routes/auth.py clip_mvp/app/api/routes/system.py clip_mvp/app/api/routes/tasks.py clip_mvp/app/api/routes/protected_files.py
& $git add clip_mvp/app/api/auth_dependencies.py clip_mvp/app/api/task_form_normalizer.py
& $git add clip_mvp/app/core clip_mvp/app/repositories clip_mvp/app/workflows
& $git add clip_mvp/app/services/auth_service.py clip_mvp/app/services/project_service.py clip_mvp/app/services/protected_file_service.py
& $git add clip_mvp/app/services/task_*.py clip_mvp/app/services/runtime_*.py
& $git add clip_mvp/frontend/src/router clip_mvp/frontend/src/stores clip_mvp/frontend/src/api/client.ts
& $git add clip_mvp/frontend/src/views
& $git add clip_mvp/frontend/src/components/TaskEventTimeline.vue clip_mvp/frontend/src/components/ReplanPanel.vue clip_mvp/frontend/src/components/RuntimePanel.vue
```

提交前检查：

```powershell
& $git diff --cached --stat
& $git diff --cached --name-only
```

如果暂存区里出现下面内容，先取消暂存：

```text
clip_mvp/.env
clip_mvp/data/
clip_mvp/uploads/
clip_mvp/audio/
clip_mvp/outputs/
clip_mvp/frontend/dist/
clip_mvp/frontend/node_modules/
third_party/
*.zip
*.log
```

取消某个错误文件：

```powershell
& $git restore --staged <文件路径>
```

确认无误后提交：

```powershell
& $git commit -m "feat(workspace): add project task runtime foundation"
```

## 5. 第三个提交：成员 A 文案闭环

成员 A 提交 ASR、知识库、文案生成、审核。

建议暂存：

```powershell
& $git add clip_mvp/app/services/asr_*.py
& $git add clip_mvp/app/services/draft_workflow_service.py clip_mvp/app/services/task_draft_phase_service.py clip_mvp/app/services/task_review_service.py
& $git add clip_mvp/app/services/llm_narration_service.py clip_mvp/app/services/llm_draft_service.py clip_mvp/app/services/llm_prompt_service.py
& $git add clip_mvp/app/services/llm_*_format_service.py clip_mvp/app/services/llm_json_format_service.py
& $git add clip_mvp/app/services/project_knowledge_service.py
& $git add clip_mvp/frontend/src/components/DraftReviewPanel.vue clip_mvp/frontend/src/components/KnowledgePanel.vue
& $git add clip_mvp/frontend/src/views/KnowledgeView.vue
& $git add clip_mvp/knowledge
```

如果文案相关字段改了 schema，也加入：

```powershell
& $git add clip_mvp/app/domain/schemas.py
```

检查后提交：

```powershell
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(draft): add ASR knowledge narration review workflow"
```

## 6. 第四个提交：成员 B 成片闭环

成员 B 提交配音、音色、上传配音、LLM 选片、时长校验、字幕音频对齐、FFmpeg 渲染、结果展示。

建议暂存：

```powershell
& $git add clip_mvp/app/services/voice_workflow_service.py
& $git add clip_mvp/app/services/tts_*.py
& $git add clip_mvp/app/services/cosyvoice_runtime_service.py
& $git add clip_mvp/app/services/voice_profile_*_service.py clip_mvp/app/services/voice_binding_service.py
& $git add clip_mvp/app/services/alignment_*.py
& $git add clip_mvp/app/services/llm_alignment_*.py
& $git add clip_mvp/app/services/task_finalize_*.py
& $git add clip_mvp/app/services/render_workflow_service.py
& $git add clip_mvp/app/services/media_*.py
& $git add clip_mvp/app/services/clip_plan_service.py
& $git add clip_mvp/app/api/routes/voice_profiles.py clip_mvp/app/api/voice_profile_presenter.py
& $git add clip_mvp/frontend/src/components/MatchedSegmentsPanel.vue
& $git add clip_mvp/frontend/src/components/ClipPlansPanel.vue
& $git add clip_mvp/frontend/src/components/TaskDetail.vue
& $git add clip_mvp/frontend/src/components/TaskCreateForm.vue
```

如果成片闭环接入字段或接口改到了这些文件，也可以加入，但提交说明要解释这是成片闭环需要：

```powershell
& $git add clip_mvp/app/domain/schemas.py
& $git add clip_mvp/app/api/routes/tasks.py
& $git add clip_mvp/frontend/src/api/client.ts
& $git add clip_mvp/frontend/src/stores/taskState.ts
& $git add clip_mvp/frontend/src/types.ts
```

检查后提交：

```powershell
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(finalize): add voice alignment rendering workflow"
```

## 7. 每次提交前必查清单

每次 `commit` 前都执行：

```powershell
& $git diff --cached --stat
& $git diff --cached --name-only
```

禁止出现：

```text
clip_mvp/.env
clip_mvp/data/
clip_mvp/uploads/
clip_mvp/audio/
clip_mvp/outputs/
clip_mvp/frontend/node_modules/
clip_mvp/frontend/dist/
third_party/
备用/
*.zip
*.log
*.db
```

如果出现，用：

```powershell
& $git restore --staged <文件路径>
```

## 8. 最终验证

所有提交完成后，跑后端语法检查：

```powershell
cd F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app
```

跑前端构建：

```powershell
cd F:\FUNASR\clip_mvp\frontend
npm run build
```

回仓库根目录检查：

```powershell
cd F:\FUNASR
& $git status --short
& $git log --oneline --decorate --max-count=12
```

## 9. 最后推送

只有验证通过后，才推集成分支：

```powershell
& $git push -u origin feature/clip-mvp-integration
```

然后在 GitHub 上创建 PR，从：

```text
feature/clip-mvp-integration -> main
```

## 10. 避免 0 changes 的规则

`0 changes` 的原因通常是：

```text
1. 目标分支已经有完全相同内容。
2. 只是删了再传，文件内容没变。
3. 后提交的人覆盖了前面已经提交过的完整项目。
4. 只做文件移动，内容没有实际差异。
```

正确做法：

```text
1. 先由集成分支接住完整项目底座。
2. 每个人在底座上提交自己负责的真实功能 diff。
3. 不要每个人都上传一份完整项目。
4. 每个人提交前看 git diff --cached --stat，确认有属于自己的代码变化。
```

## 11. 成员 B 自查口径

成员 B 的提交说明可以这样写：

```text
本提交负责确认文案后的成片闭环：
- 支持 TTS/音色/上传配音。
- 读取每段配音真实时长。
- 调用 LLM 按语义和时长选择原视频片段。
- 校验选片结果并保存 matched segments / clip plan。
- 使用 FFmpeg 渲染 MP4、SRT、EDL。
- 在任务详情页展示选片、方案、结果预览和下载。
```

这样老师或队友看提交记录时，能明确看出这不是简单替换文件，而是一条完整业务闭环。

## 12. 三天分批上传总计划

这个计划适合“每天传一点”，但不要每天合进 `main`。每天只推送到同一个集成分支：

```text
feature/clip-mvp-integration
```

第 1 天目标：

```text
仓库结构清理 + 项目底座 + 每个成员先提交一部分独立模块。
```

第 2 天目标：

```text
任务主流程接起来：C 接任务运行，A 接文案闭环，B 接配音和选片后端。
```

第 3 天目标：

```text
成片渲染、前端结果展示、文档和最终验证。
```

每天结束都做一次：

```powershell
cd F:\FUNASR
& $git status --short
& $git log --oneline --decorate --max-count=12
& $git push -u origin feature/clip-mvp-integration
```

第 2 天和第 3 天如果已经设置过 upstream，可以简写：

```powershell
& $git push
```

## 13. 每天开始前固定动作

每天开始前，所有人先同步集成分支：

```powershell
cd F:\FUNASR
$git = 'D:\软工实训\Git\cmd\git.exe'
& $git fetch origin
& $git switch feature/clip-mvp-integration
& $git pull --ff-only origin feature/clip-mvp-integration
& $git status --short --branch
```

如果 `pull --ff-only` 失败，说明有人改了同一批文件，先不要强推，不要 reset，找负责人处理冲突。

## 14. 每个成员提交前固定动作

每个人提交前先设置自己的 Git 身份。否则 GitHub 可能不把贡献算到个人账号。

成员 A 示例：

```powershell
& $git config user.name "Member A"
& $git config user.email "member-a@example.com"
```

成员 B 示例：

```powershell
& $git config user.name "Member B"
& $git config user.email "member-b@example.com"
```

成员 C 示例：

```powershell
& $git config user.name "Member C"
& $git config user.email "member-c@example.com"
```

提交前必须确认身份：

```powershell
& $git config user.name
& $git config user.email
```

如果三个人共用一台电脑，每个人提交自己的 commit 前都要重新设置一次。

## 15. 每个 commit 固定五步

每个 commit 都按这个模板做：

```powershell
& $git status --short
& $git add <本次提交的文件路径>
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "<提交信息>"
```

如果 `diff --cached --stat` 没有显示代码变化，说明这个 commit 很可能会变成 `0 changes`，先不要提交。

如果暂存错了文件，用：

```powershell
& $git restore --staged <文件路径>
```

## 16. 第 1 天详细提交计划

第 1 天顺序不能乱：先仓库清理，再 C 的底座，然后 A/B 提交独立模块。

### D1-0 集成负责人：仓库清理

提交内容：

```text
.gitignore
clip_mvp/.gitignore
clip_mvp/.env.example
clip_mvp/requirements.txt
clip_mvp/docs/
clip_mvp/scripts/
```

命令：

```powershell
& $git add .gitignore clip_mvp/.gitignore clip_mvp/.env.example clip_mvp/requirements.txt clip_mvp/docs clip_mvp/scripts
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "chore(repo): prepare clip_mvp repository layout"
```

检查关键文件没有被 `.gitignore` 误伤：

```powershell
& $git check-ignore -v clip_mvp/app/main.py clip_mvp/app/workflows/templates/narration_clip.json clip_mvp/app/workflows/templates/script_match_clip.json
```

正常情况：没有输出。

### D1-C1 成员 C：应用入口、配置、鉴权底座

提交内容：

```text
clip_mvp/app/main.py
clip_mvp/app/config.py
clip_mvp/app/core/
clip_mvp/app/api/auth_dependencies.py
clip_mvp/app/api/routes/auth.py
clip_mvp/app/services/auth_service.py
```

命令：

```powershell
& $git add clip_mvp/app/main.py clip_mvp/app/config.py clip_mvp/app/core
& $git add clip_mvp/app/api/auth_dependencies.py clip_mvp/app/api/routes/auth.py
& $git add clip_mvp/app/services/auth_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(auth): add app bootstrap and login foundation"
```

### D1-C2 成员 C：项目、数据库、基础 repository

提交内容：

```text
clip_mvp/app/db.py
clip_mvp/app/repositories/
clip_mvp/app/services/project_service.py
clip_mvp/app/api/routes/system.py
```

命令：

```powershell
& $git add clip_mvp/app/db.py clip_mvp/app/repositories
& $git add clip_mvp/app/services/project_service.py clip_mvp/app/api/routes/system.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(projects): add project persistence foundation"
```

### D1-C3 成员 C：前端壳、路由、状态管理

提交内容：

```text
clip_mvp/frontend/package.json
clip_mvp/frontend/package-lock.json
clip_mvp/frontend/tsconfig.json
clip_mvp/frontend/vite.config.ts
clip_mvp/frontend/index.html
clip_mvp/frontend/src/main.ts
clip_mvp/frontend/src/App.vue
clip_mvp/frontend/src/router/
clip_mvp/frontend/src/stores/
clip_mvp/frontend/src/api/client.ts
clip_mvp/frontend/src/styles.css
clip_mvp/frontend/src/types.ts
```

命令：

```powershell
& $git add clip_mvp/frontend/package.json clip_mvp/frontend/package-lock.json clip_mvp/frontend/tsconfig.json clip_mvp/frontend/vite.config.ts clip_mvp/frontend/index.html
& $git add clip_mvp/frontend/src/main.ts clip_mvp/frontend/src/App.vue clip_mvp/frontend/src/router clip_mvp/frontend/src/stores clip_mvp/frontend/src/api/client.ts
& $git add clip_mvp/frontend/src/styles.css clip_mvp/frontend/src/types.ts
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(frontend): add Vue app shell and shared state"
```

### D1-A1 成员 A：ASR 和字幕缓存

提交内容：

```text
clip_mvp/app/services/asr_service.py
clip_mvp/app/services/asr_workflow_service.py
clip_mvp/app/repositories/sqlite_asr_cache_repository.py
clip_mvp/app/services/llm_subtitle_format_service.py
```

命令：

```powershell
& $git add clip_mvp/app/services/asr_service.py clip_mvp/app/services/asr_workflow_service.py
& $git add clip_mvp/app/repositories/sqlite_asr_cache_repository.py
& $git add clip_mvp/app/services/llm_subtitle_format_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(asr): add subtitle extraction and cache workflow"
```

### D1-A2 成员 A：知识库基础

提交内容：

```text
clip_mvp/app/services/project_knowledge_service.py
clip_mvp/frontend/src/components/KnowledgePanel.vue
clip_mvp/frontend/src/views/KnowledgeView.vue
clip_mvp/knowledge/
```

命令：

```powershell
& $git add clip_mvp/app/services/project_knowledge_service.py
& $git add clip_mvp/frontend/src/components/KnowledgePanel.vue clip_mvp/frontend/src/views/KnowledgeView.vue
& $git add clip_mvp/knowledge
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(knowledge): add project knowledge context workflow"
```

### D1-B1 成员 B：音色模板和配音 API

提交内容：

```text
clip_mvp/app/api/routes/voice_profiles.py
clip_mvp/app/api/voice_profile_presenter.py
clip_mvp/app/repositories/sqlite_voice_profile_repository.py
clip_mvp/app/services/voice_profile_service.py
clip_mvp/app/services/voice_profile_manifest_service.py
clip_mvp/app/services/voice_profile_upload_service.py
```

命令：

```powershell
& $git add clip_mvp/app/api/routes/voice_profiles.py clip_mvp/app/api/voice_profile_presenter.py
& $git add clip_mvp/app/repositories/sqlite_voice_profile_repository.py
& $git add clip_mvp/app/services/voice_profile_service.py clip_mvp/app/services/voice_profile_manifest_service.py clip_mvp/app/services/voice_profile_upload_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(voice): add voice profile management"
```

### D1-B2 成员 B：TTS provider 和 CosyVoice 运行封装

提交内容：

```text
clip_mvp/app/services/cosyvoice_runtime_service.py
clip_mvp/app/services/tts_provider_config_service.py
clip_mvp/app/services/tts_provider_service.py
clip_mvp/app/services/tts_cosyvoice_http_provider.py
clip_mvp/app/services/tts_cosyvoice_local_provider.py
clip_mvp/app/services/tts_mock_provider.py
clip_mvp/app/services/tts_voice_target_service.py
clip_mvp/app/tools/cosyvoice_local_helper.py
clip_mvp/app/tools/cosyvoice_local_server.py
```

命令：

```powershell
& $git add clip_mvp/app/services/cosyvoice_runtime_service.py
& $git add clip_mvp/app/services/tts_provider_config_service.py clip_mvp/app/services/tts_provider_service.py
& $git add clip_mvp/app/services/tts_cosyvoice_http_provider.py clip_mvp/app/services/tts_cosyvoice_local_provider.py clip_mvp/app/services/tts_mock_provider.py clip_mvp/app/services/tts_voice_target_service.py
& $git add clip_mvp/app/tools/cosyvoice_local_helper.py clip_mvp/app/tools/cosyvoice_local_server.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(tts): add CosyVoice provider runtime"
```

第 1 天结束验证：

```powershell
cd F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app

cd F:\FUNASR\clip_mvp\frontend
npm run build

cd F:\FUNASR
& $git status --short
& $git push -u origin feature/clip-mvp-integration
```

## 17. 第 2 天详细提交计划

第 2 天目标是把主工作流接起来。每天开始前先执行第 13 节同步命令。

### D2-C1 成员 C：任务生命周期和事件追踪

提交内容：

```text
clip_mvp/app/services/task_service.py
clip_mvp/app/services/task_lifecycle_service.py
clip_mvp/app/services/task_state_service.py
clip_mvp/app/services/task_store_service.py
clip_mvp/app/services/task_query_service.py
clip_mvp/app/services/task_event_service.py
clip_mvp/app/services/task_artifact_service.py
clip_mvp/app/api/routes/tasks.py
```

命令：

```powershell
& $git add clip_mvp/app/services/task_service.py clip_mvp/app/services/task_lifecycle_service.py clip_mvp/app/services/task_state_service.py
& $git add clip_mvp/app/services/task_store_service.py clip_mvp/app/services/task_query_service.py clip_mvp/app/services/task_event_service.py clip_mvp/app/services/task_artifact_service.py
& $git add clip_mvp/app/api/routes/tasks.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(tasks): add task lifecycle and event tracking"
```

### D2-C2 成员 C：任务 worker 和工作流模板

提交内容：

```text
clip_mvp/app/services/task_bootstrap_service.py
clip_mvp/app/services/task_factory_service.py
clip_mvp/app/services/task_runner_service.py
clip_mvp/app/services/task_worker_service.py
clip_mvp/app/services/task_run_context_service.py
clip_mvp/app/workflows/
```

命令：

```powershell
& $git add clip_mvp/app/services/task_bootstrap_service.py clip_mvp/app/services/task_factory_service.py
& $git add clip_mvp/app/services/task_runner_service.py clip_mvp/app/services/task_worker_service.py clip_mvp/app/services/task_run_context_service.py
& $git add clip_mvp/app/workflows
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(workflow): add task runner and workflow templates"
```

### D2-C3 成员 C：任务页面和运行状态页面

提交内容：

```text
clip_mvp/frontend/src/views/DashboardView.vue
clip_mvp/frontend/src/views/LoginView.vue
clip_mvp/frontend/src/views/ProjectWorkspaceView.vue
clip_mvp/frontend/src/views/ProjectSettingsView.vue
clip_mvp/frontend/src/views/TasksView.vue
clip_mvp/frontend/src/views/RuntimeView.vue
clip_mvp/frontend/src/views/CreateTaskView.vue
clip_mvp/frontend/src/views/TaskDetailView.vue
clip_mvp/frontend/src/components/RuntimePanel.vue
clip_mvp/frontend/src/components/TaskEventTimeline.vue
```

命令：

```powershell
& $git add clip_mvp/frontend/src/views/DashboardView.vue clip_mvp/frontend/src/views/LoginView.vue
& $git add clip_mvp/frontend/src/views/ProjectWorkspaceView.vue clip_mvp/frontend/src/views/ProjectSettingsView.vue clip_mvp/frontend/src/views/TasksView.vue
& $git add clip_mvp/frontend/src/views/RuntimeView.vue clip_mvp/frontend/src/views/CreateTaskView.vue clip_mvp/frontend/src/views/TaskDetailView.vue
& $git add clip_mvp/frontend/src/components/RuntimePanel.vue clip_mvp/frontend/src/components/TaskEventTimeline.vue
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(workspace): add task and runtime pages"
```

### D2-A1 成员 A：LLM 文案 prompt 和格式化

提交内容：

```text
clip_mvp/app/services/llm_service.py
clip_mvp/app/services/llm_prompt_service.py
clip_mvp/app/services/llm_format_service.py
clip_mvp/app/services/llm_json_format_service.py
clip_mvp/app/services/llm_grounding_format_service.py
```

命令：

```powershell
& $git add clip_mvp/app/services/llm_service.py clip_mvp/app/services/llm_prompt_service.py
& $git add clip_mvp/app/services/llm_format_service.py clip_mvp/app/services/llm_json_format_service.py clip_mvp/app/services/llm_grounding_format_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(llm): add grounded narration prompt formatting"
```

### D2-A2 成员 A：文案生成、拆 beat、审核保存

提交内容：

```text
clip_mvp/app/services/llm_narration_service.py
clip_mvp/app/services/llm_draft_service.py
clip_mvp/app/services/draft_workflow_service.py
clip_mvp/app/services/task_draft_phase_service.py
clip_mvp/app/services/task_review_service.py
```

命令：

```powershell
& $git add clip_mvp/app/services/llm_narration_service.py clip_mvp/app/services/llm_draft_service.py
& $git add clip_mvp/app/services/draft_workflow_service.py clip_mvp/app/services/task_draft_phase_service.py clip_mvp/app/services/task_review_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(draft): add narration draft and review workflow"
```

### D2-A3 成员 A：文案审核前端

提交内容：

```text
clip_mvp/frontend/src/components/DraftReviewPanel.vue
clip_mvp/frontend/src/components/TaskHistory.vue
```

命令：

```powershell
& $git add clip_mvp/frontend/src/components/DraftReviewPanel.vue clip_mvp/frontend/src/components/TaskHistory.vue
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(review): add draft review editing UI"
```

### D2-B1 成员 B：TTS 生成和配音时长

提交内容：

```text
clip_mvp/app/services/tts_service.py
clip_mvp/app/services/tts_cache_service.py
clip_mvp/app/services/tts_text_chunker.py
clip_mvp/app/services/voice_binding_service.py
clip_mvp/app/services/voice_workflow_service.py
```

命令：

```powershell
& $git add clip_mvp/app/services/tts_service.py clip_mvp/app/services/tts_cache_service.py clip_mvp/app/services/tts_text_chunker.py
& $git add clip_mvp/app/services/voice_binding_service.py clip_mvp/app/services/voice_workflow_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(voice): add beat voice synthesis workflow"
```

### D2-B2 成员 B：LLM 选片和时长校验

提交内容：

```text
clip_mvp/app/services/alignment_duration_service.py
clip_mvp/app/services/alignment_subtitle_service.py
clip_mvp/app/services/alignment_workflow_service.py
clip_mvp/app/services/llm_alignment_service.py
clip_mvp/app/services/llm_alignment_format_service.py
```

命令：

```powershell
& $git add clip_mvp/app/services/alignment_duration_service.py clip_mvp/app/services/alignment_subtitle_service.py clip_mvp/app/services/alignment_workflow_service.py
& $git add clip_mvp/app/services/llm_alignment_service.py clip_mvp/app/services/llm_alignment_format_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(alignment): add duration aware source selection"
```

### D2-B3 成员 B：finalize 规划链路

提交内容：

```text
clip_mvp/app/services/task_finalize_plan_models.py
clip_mvp/app/services/task_finalize_plan_validation_service.py
clip_mvp/app/services/task_finalize_planning_service.py
clip_mvp/app/services/task_finalize_script_planner.py
clip_mvp/app/services/task_finalize_voice_planner.py
clip_mvp/app/services/task_finalize_workflow_service.py
```

命令：

```powershell
& $git add clip_mvp/app/services/task_finalize_plan_models.py clip_mvp/app/services/task_finalize_plan_validation_service.py
& $git add clip_mvp/app/services/task_finalize_planning_service.py clip_mvp/app/services/task_finalize_script_planner.py
& $git add clip_mvp/app/services/task_finalize_voice_planner.py clip_mvp/app/services/task_finalize_workflow_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(finalize): add planning workflow for reviewed scripts"
```

第 2 天结束验证和推送：

```powershell
cd F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app

cd F:\FUNASR\clip_mvp\frontend
npm run build

cd F:\FUNASR
& $git status --short
& $git push
```

## 18. 第 3 天详细提交计划

第 3 天目标是把最终输出、前端展示和文档补齐。

### D3-C1 成员 C：受保护文件和运行状态收口

提交内容：

```text
clip_mvp/app/api/routes/protected_files.py
clip_mvp/app/services/protected_file_service.py
clip_mvp/app/services/runtime_service.py
clip_mvp/app/services/runtime_probe_service.py
clip_mvp/app/services/runtime_cosyvoice_status_service.py
clip_mvp/frontend/src/components/ReplanPanel.vue
```

命令：

```powershell
& $git add clip_mvp/app/api/routes/protected_files.py clip_mvp/app/services/protected_file_service.py
& $git add clip_mvp/app/services/runtime_service.py clip_mvp/app/services/runtime_probe_service.py clip_mvp/app/services/runtime_cosyvoice_status_service.py
& $git add clip_mvp/frontend/src/components/ReplanPanel.vue
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(runtime): add protected files and runtime status"
```

### D3-A1 成员 A：事实约束和文案质量收口

提交内容：

```text
clip_mvp/app/services/llm_prompt_service.py
clip_mvp/app/services/llm_draft_service.py
clip_mvp/app/services/draft_workflow_service.py
clip_mvp/app/domain/schemas.py
```

命令：

```powershell
& $git add clip_mvp/app/services/llm_prompt_service.py clip_mvp/app/services/llm_draft_service.py clip_mvp/app/services/draft_workflow_service.py
& $git add clip_mvp/app/domain/schemas.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "fix(draft): enforce context facts and beat quality checks"
```

### D3-B1 成员 B：媒体处理和渲染输出

提交内容：

```text
clip_mvp/app/services/media_probe_service.py
clip_mvp/app/services/media_audio_service.py
clip_mvp/app/services/media_video_service.py
clip_mvp/app/services/media_export_service.py
clip_mvp/app/services/media_service.py
clip_mvp/app/services/render_workflow_service.py
clip_mvp/app/services/task_finalize_output_service.py
clip_mvp/app/services/clip_plan_service.py
clip_mvp/app/repositories/sqlite_clip_plan_repository.py
```

命令：

```powershell
& $git add clip_mvp/app/services/media_probe_service.py clip_mvp/app/services/media_audio_service.py clip_mvp/app/services/media_video_service.py
& $git add clip_mvp/app/services/media_export_service.py clip_mvp/app/services/media_service.py clip_mvp/app/services/render_workflow_service.py
& $git add clip_mvp/app/services/task_finalize_output_service.py clip_mvp/app/services/clip_plan_service.py
& $git add clip_mvp/app/repositories/sqlite_clip_plan_repository.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(render): add media export and clip plan output"
```

### D3-B2 成员 B：成片结果前端展示

提交内容：

```text
clip_mvp/frontend/src/components/MatchedSegmentsPanel.vue
clip_mvp/frontend/src/components/ClipPlansPanel.vue
clip_mvp/frontend/src/components/TaskDetail.vue
clip_mvp/frontend/src/components/TaskCreateForm.vue
clip_mvp/frontend/src/utils/format.ts
```

命令：

```powershell
& $git add clip_mvp/frontend/src/components/MatchedSegmentsPanel.vue clip_mvp/frontend/src/components/ClipPlansPanel.vue
& $git add clip_mvp/frontend/src/components/TaskDetail.vue clip_mvp/frontend/src/components/TaskCreateForm.vue
& $git add clip_mvp/frontend/src/utils/format.ts
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "feat(finalize-ui): add voice render result panels"
```

### D3-B3 成员 B：字幕和配音对齐修复

如果第 3 天需要把字幕和音频对齐问题单独体现，单独做这个 commit。

提交内容：

```text
clip_mvp/app/services/media_export_service.py
clip_mvp/app/services/media_service.py
clip_mvp/app/services/render_workflow_service.py
```

命令：

```powershell
& $git add clip_mvp/app/services/media_export_service.py clip_mvp/app/services/media_service.py clip_mvp/app/services/render_workflow_service.py
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "fix(subtitles): align subtitle cues with final voice timeline"
```

### D3-ALL1 全员：最终文档和验收记录

提交内容：

```text
clip_mvp/docs/
```

命令：

```powershell
& $git add clip_mvp/docs
& $git diff --cached --stat
& $git diff --cached --name-only
& $git commit -m "docs(team): add submission plan and validation notes"
```

第 3 天最终验证：

```powershell
cd F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app
E:\anaconda\envs\funasr-env\python.exe -c "from app.main import app; print('APP_IMPORT_OK', bool(app))"

cd F:\FUNASR\clip_mvp\frontend
npm run build

cd F:\FUNASR
& $git status --short
& $git log --oneline --decorate --max-count=30
& $git push
```

## 19. 三天计划的提交数量建议

建议最终提交数：

```text
集成负责人：2 个 commit
成员 A：5 到 6 个 commit
成员 B：7 到 8 个 commit
成员 C：6 到 7 个 commit
```

这样每个人都有连续、可解释的功能提交，不会像一次性替换项目那样出现贡献不清晰。

## 20. 每天上传后 GitHub 检查

每天 push 后，在 GitHub 上看集成分支，不要只看本地。

检查项：

```text
1. 分支是不是 feature/clip-mvp-integration。
2. Commits 页面里有没有当天每个人的 commit。
3. 每个 commit 点进去有没有实际 Files changed。
4. Files changed 里有没有 .env、数据库、视频、音频、zip、third_party。
5. 如果某个 commit 是 0 changes，说明它没有真实差异，后续不要继续重复覆盖上传。
```

如果成员的 commit 没算到个人贡献，通常是邮箱没有绑定 GitHub。先去 GitHub 账号设置里绑定提交用的邮箱，再继续提交。

## 21. 多人同时改同一个文件的处理规则

这些文件容易多人都要改：

```text
clip_mvp/app/domain/schemas.py
clip_mvp/app/api/routes/tasks.py
clip_mvp/frontend/src/api/client.ts
clip_mvp/frontend/src/types.ts
clip_mvp/frontend/src/components/TaskCreateForm.vue
clip_mvp/frontend/src/components/TaskDetail.vue
```

规则：

```text
1. 谁的功能先接入，谁先提交。
2. 后一个人提交前必须先 pull --ff-only。
3. 同一个文件不要三个人同时离线改。
4. 如果要改同一个文件，先在群里说“我现在改哪个文件”。
5. 冲突不要强行覆盖，先看双方改动再合并。
```

## 22. 如果老师要求“每天都有代码量”

每天每个人至少做一个真实 commit，不要为了代码量乱改格式。

成员 A 每天可以这样分：

```text
第 1 天：ASR、知识库基础。
第 2 天：LLM 文案生成、审核。
第 3 天：事实约束、质量修复、文档。
```

成员 B 每天可以这样分：

```text
第 1 天：音色模板、TTS provider。
第 2 天：配音生成、LLM 选片、finalize 规划。
第 3 天：渲染输出、字幕对齐、结果展示。
```

成员 C 每天可以这样分：

```text
第 1 天：登录、项目、前端壳。
第 2 天：任务生命周期、worker、工作流模板。
第 3 天：运行状态、文件保护、最终仓库清理。
```

这样每天都有真实业务模块提交，GitHub 上也能解释清楚。

## 23. 仓库在成员 B 账号下时的处理方式

如果远程仓库在成员 B 的 GitHub 账号下，成员 B 同时有两个身份：

```text
身份 1：仓库管理员，负责建分支、看 PR、最后合并。
身份 2：成员 B，负责配音、选片、渲染、成片结果展示。
```

这两个身份要分开。不要因为仓库在成员 B 账号下，就让成员 B 代替 A/C 提交所有代码。

推荐权限方案：

```text
1. 成员 B 保留仓库 owner 权限。
2. 把成员 A、成员 C 加为 collaborator。
3. A/C 用自己的 GitHub 账号和邮箱提交代码。
4. A/C 可以推自己的分支，也可以按顺序推 feature/clip-mvp-integration。
5. 成员 B 只负责检查和最后合并，不改写 A/C 的提交作者。
```

如果不想让所有人直接推集成分支，可以改成每个人一个分支：

```text
feature/member-c-workspace-runtime
feature/member-a-draft-review
feature/member-b-finalize-render
```

然后由成员 B 在 GitHub 上合并到：

```text
feature/clip-mvp-integration
```

最后再从：

```text
feature/clip-mvp-integration -> main
```

这种方式最清晰，但操作比单一集成分支多一点。

### 成员 B 作为 owner 的每日工作

每天开始：

```powershell
cd F:\FUNASR
$git = 'D:\软工实训\Git\cmd\git.exe'
& $git fetch origin
& $git switch feature/clip-mvp-integration
& $git pull --ff-only origin feature/clip-mvp-integration
```

每天结束，成员 B 检查：

```powershell
& $git status --short
& $git log --oneline --decorate --max-count=30
```

重点看：

```text
1. 有没有 A/C/B 三个人当天的 commit。
2. 每个 commit 作者是不是对应成员本人。
3. 有没有 .env、数据库、视频、音频、zip、third_party。
4. 有没有把旧根目录删除误提交。
5. 有没有 0 changes 或只有格式化、空替换的提交。
```

### 成员 B 自己提交前必须切回自己的身份

因为仓库在成员 B 账号下，成员 B 提交自己的功能前设置：

```powershell
& $git config user.name "成员B的GitHub用户名"
& $git config user.email "成员B绑定GitHub的邮箱"
```

确认：

```powershell
& $git config user.name
& $git config user.email
```

然后只提交成员 B 文件，不要把 A/C 文件顺手提交进去。

### A/C 如果在成员 B 电脑上提交

如果 A/C 没有自己电脑，临时在成员 B 电脑上提交，必须先切换 Git 身份：

```powershell
& $git config user.name "成员A的GitHub用户名"
& $git config user.email "成员A绑定GitHub的邮箱"
```

成员 A 提交完成后，成员 B 再提交自己的代码前，要切回来：

```powershell
& $git config user.name "成员B的GitHub用户名"
& $git config user.email "成员B绑定GitHub的邮箱"
```

否则会出现两种问题：

```text
1. 成员 A 的提交算到成员 B 名下。
2. 成员 B 的提交算到成员 A 名下。
```

### 如果只能由成员 B 统一 push

可以由成员 B 统一 push，但不建议由成员 B 统一 commit。

原因：

```text
push 人是谁不重要，commit author 才决定 GitHub 贡献归属。
```

也就是说：

```text
成员 A 自己 commit，成员 B 帮忙 push，可以接受。
成员 B 用自己的身份替 A commit，不建议。
```

如果必须代提交，至少要用对应成员的 author 信息：

```powershell
& $git commit --author="成员A的GitHub用户名 <成员A绑定GitHub的邮箱>" -m "feat(draft): add narration draft workflow"
```

但这个方式只适合临时补救。正常还是让每个人自己提交。

### 成员 B 的最终解释口径

如果老师问为什么仓库在成员 B 账号下，但有多人提交，可以这样解释：

```text
仓库由成员 B 创建和维护，所以远程 owner 是成员 B。
团队按业务闭环分工，A/C/B 分别使用自己的 Git 身份提交。
成员 B 作为 owner 只负责集成分支、PR 和最终合并，不代表所有代码都由成员 B 完成。
成员 B 本人的代码集中在配音、选片、渲染和结果展示闭环。
```
