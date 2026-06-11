@echo off
setlocal
cd /d "%~dp0\.."

if not exist ".env" (
  echo [ERROR] .env not found.
  echo Copy .env.example to .env first.
  pause
  exit /b 1
)

if "%BACKEND_PYTHON%"=="" (
  set "BACKEND_PYTHON=python"
)

echo Starting or checking CosyVoice service at http://127.0.0.1:50000
echo Python: %BACKEND_PYTHON%
"%BACKEND_PYTHON%" -c "from app.services.cosyvoice_runtime_service import cosyvoice_runtime_service; print(cosyvoice_runtime_service.ensure_service_running())"
pause
