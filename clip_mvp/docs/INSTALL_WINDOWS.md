# Clip MVP Windows Local Install

This project is intended to run locally on Windows.

## 1. Required Runtime

- Python 3.10 or a Conda environment.
- FFmpeg and FFprobe available in `PATH`.
- A working OpenAI-compatible LLM API key.
- Optional GPU/CUDA for faster FunASR and CosyVoice.

## 2. Package Layout

Keep these directories together:

```text
FUNASR/
  clip_mvp/
  third_party/
    CosyVoice/
    cosyvoice-env-win/
    models/
```

`clip_mvp` is the application. `third_party` contains CosyVoice runtime, models, and cache.

## 3. Configure

In `clip_mvp`, copy `.env.example` to `.env`.

Fill at least:

```text
LLM_API_KEY=your_key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

If your CosyVoice paths differ from the default package layout, uncomment and edit:

```text
COSYVOICE_LOCAL_PYTHON=
COSYVOICE_REPO_DIR=
COSYVOICE_MODEL_DIR=
COSYVOICE_CACHE_DIR=
```

## 4. Install Backend Dependencies

Use your backend Python environment:

```bat
cd /d F:\FUNASR\clip_mvp
python -m pip install -r requirements.txt
```

If you use Conda, activate the environment first or set `BACKEND_PYTHON` before running scripts:

```bat
set BACKEND_PYTHON=E:\anaconda\envs\funasr-env\python.exe
```

## 5. Build Frontend

If `frontend/dist` is already included, this step can be skipped.

```bat
cd /d F:\FUNASR\clip_mvp\frontend
npm install
npm run build
```

## 6. Check Environment

```bat
cd /d F:\FUNASR\clip_mvp
python scripts\check_env.py
```

Fix any `[FAIL]` item before running.

## 7. Start

Start CosyVoice service:

```bat
scripts\start_cosyvoice.bat
```

Start backend:

```bat
scripts\start_backend.bat
```

Open:

```text
http://127.0.0.1:8010
```

## 8. What Not To Package

Exclude these generated or private paths:

```text
clip_mvp/.env
clip_mvp/uploads/
clip_mvp/audio/
clip_mvp/outputs/
clip_mvp/data/*.db
clip_mvp/data/tmp/
clip_mvp/frontend/node_modules/
```

Also exclude API keys and private source videos.
