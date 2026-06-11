# Clip MVP 本地启动文档

本文档用于说明如何在 Windows 本地环境启动 Clip MVP 项目。

## 1. 进入项目目录

```powershell
cd "C:\Users\epsilon\Desktop\项目\创新项目实践\clip_mvp (2)"
```

如果你的项目目录不同，请替换为实际路径。

## 2. 必需环境

本项目本地启动至少需要：

- Python 3.10
- Python 依赖包
- FFmpeg / FFprobe
- `.env` 配置文件
- OpenAI 兼容的 LLM API Key

可选组件：

- CosyVoice：用于 TTS / 配音能力
- CUDA / GPU：用于加速 FunASR 和 CosyVoice

## 3. 检查 Python 3.10

```powershell
py -3.10 --version
```

期望输出类似：

```text
Python 3.10.11
```

如果没有 Python 3.10，可使用 Python Launcher 安装：

```powershell
py install 3.10
```

## 4. 安装 Python 依赖

```powershell
py -3.10 -m pip install -r requirements.txt
```

本项目依赖包括 FastAPI、Uvicorn、OpenAI SDK、FunASR、ModelScope 等。

## 5. 配置 `.env`

如果项目根目录没有 `.env` 文件，先复制示例配置：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`，至少填写：

```text
LLM_API_KEY=你的_API_Key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

如果使用其他 OpenAI 兼容服务，请替换 `LLM_BASE_URL` 和 `LLM_MODEL`。

## 6. 安装 FFmpeg

项目需要 `ffmpeg` 和 `ffprobe` 处理音视频。

如果已安装 Chocolatey，可以执行：

```powershell
C:\ProgramData\chocolatey\bin\choco.exe install ffmpeg -y
```

如果当前终端识别不到 `choco`，可临时补充 PATH：

```powershell
$env:Path += ";C:\ProgramData\chocolatey\bin"
```

验证 FFmpeg：

```powershell
ffmpeg -version
ffprobe -version
```

如果命令不可用，请重新打开 PowerShell，或确认 `C:\ProgramData\chocolatey\bin` 已加入系统 PATH。

## 7. 检查项目环境

```powershell
$env:Path += ";C:\ProgramData\chocolatey\bin"
py -3.10 scripts\check_env.py
```

关键检查项：

- `.env exists`
- `python module fastapi`
- `python module uvicorn`
- `python module openai`
- `python module pydantic_settings`
- `python module requests`
- `ffmpeg`
- `ffprobe`
- `backend import True`

如果看到 CosyVoice 相关 `[WARN]`，通常不影响基础后端启动，但会影响 TTS / 配音功能。

## 8. 启动后端服务

推荐直接使用 Python 3.10 启动：

```powershell
$env:Path += ";C:\ProgramData\chocolatey\bin"
py -3.10 -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

启动成功后会看到类似输出：

```text
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8010
```

## 9. 访问项目

浏览器打开：

```text
http://127.0.0.1:8010/
```

健康检查地址：

```text
http://127.0.0.1:8010/api/health
```

也可以用 PowerShell 验证：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/health"
```

期望输出：

```text
status project
------ -------
ok     Clip MVP
```

## 10. 可选：启动 CosyVoice

如果你需要 TTS / 配音功能，并且已经准备好 `third_party` 目录中的 CosyVoice 环境、模型和缓存，可以启动 CosyVoice 服务：

```powershell
scripts\start_cosyvoice.bat
```

默认后端会访问：

```text
http://127.0.0.1:50000
```

相关配置位于 `.env`：

```text
COSYVOICE_BASE_URL=http://127.0.0.1:50000
COSYVOICE_SFT_ENDPOINT=/inference_sft
```

## 11. 常见问题

### 11.1 `python` 不是 Python 3.10

不要直接使用：

```powershell
python -m uvicorn app.main:app
```

推荐固定使用：

```powershell
py -3.10 -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

### 11.2 `choco` 无法识别

Chocolatey 可能已安装，但 PATH 未刷新。可使用完整路径：

```powershell
C:\ProgramData\chocolatey\bin\choco.exe --version
```

或临时补充 PATH：

```powershell
$env:Path += ";C:\ProgramData\chocolatey\bin"
```

### 11.3 `ffmpeg not found in PATH`

先确认 FFmpeg 是否能通过 Chocolatey 路径找到：

```powershell
$env:Path += ";C:\ProgramData\chocolatey\bin"
ffmpeg -version
ffprobe -version
```

如果仍不可用，重新安装：

```powershell
C:\ProgramData\chocolatey\bin\choco.exe install ffmpeg -y
```

### 11.4 `TTS profile manifest not found`

类似日志：

```text
TTS profile manifest not found: ...\data\tts_profiles.json
```

这表示本地缺少 TTS 语音模板配置。它通常不影响基础后端启动，但会影响 TTS / 配音功能。

### 11.5 CosyVoice 相关 WARN

如果环境检查出现：

```text
[WARN] CosyVoice Python missing
[WARN] CosyVoice repo missing
[WARN] Default CosyVoice model missing
```

说明 `third_party` 下的 CosyVoice 环境或模型未配置。基础页面和非 TTS 功能仍可启动，但配音相关功能不可用。

## 12. 最小启动命令汇总

在项目根目录执行：

```powershell
$env:Path += ";C:\ProgramData\chocolatey\bin"
py -3.10 scripts\check_env.py
py -3.10 -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

然后访问：

```text
http://127.0.0.1:8010/
```
