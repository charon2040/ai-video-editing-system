# Three Person Submission Plan

Use three commits or three pull requests. Do not commit `third_party`, `.env`, generated videos, databases, logs, or `frontend/dist`.

## Person 1: Backend Workflow

Responsible scope:

```text
clip_mvp/app/
clip_mvp/pyproject.toml
clip_mvp/requirements.txt
clip_mvp/run.py
```

Suggested commit message:

```text
feat(backend): implement AI clip workflow and service architecture
```

Before submitting:

```bat
cd /d F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe -m compileall app
E:\anaconda\envs\funasr-env\python.exe -c "from app.main import app; print('APP_IMPORT_OK', bool(app))"
```

## Person 2: Frontend UI

Responsible scope:

```text
clip_mvp/frontend/
```

Do not include:

```text
clip_mvp/frontend/node_modules/
clip_mvp/frontend/dist/
```

Suggested commit message:

```text
feat(frontend): add project workspace and task workflow UI
```

Before submitting:

```bat
cd /d F:\FUNASR\clip_mvp\frontend
npm run build
```

## Person 3: Packaging, Docs, Repository Cleanup

Responsible scope:

```text
.gitignore
clip_mvp/.env.example
clip_mvp/.gitignore
clip_mvp/README.md
clip_mvp/docs/
clip_mvp/scripts/
clip_mvp/knowledge/
```

Also responsible for removing the old root-level demo layout from Git:

```text
backend/
frontend/
README.md
PROJECT_ARCHITECTURE.md
requirements.txt
.env.example
```

Suggested commit message:

```text
chore(packaging): prepare Windows local delivery package
```

Before submitting:

```bat
cd /d F:\FUNASR\clip_mvp
E:\anaconda\envs\funasr-env\python.exe scripts\check_env.py
```

## Recommended Commit Order

1. Person 1 submits backend workflow.
2. Person 2 submits frontend UI.
3. Person 3 submits packaging docs, cleanup, and `.gitignore`.

This order keeps the app runnable after each commit and avoids committing private runtime assets.
