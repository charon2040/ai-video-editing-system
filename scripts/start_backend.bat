@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".env" (
  echo [ERROR] .env not found.
  echo Copy .env.example to .env and fill LLM_API_KEY first.
  pause
  exit /b 1
)

if "%BACKEND_PYTHON%"=="" (
  set "BACKEND_PYTHON=python"
)

echo Starting Clip MVP backend at http://127.0.0.1:8010
echo Python: %BACKEND_PYTHON%
"%BACKEND_PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port 8010
pause
