from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY = ROOT.parent / "third_party"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def ok(label: str, value: object = "") -> None:
    suffix = f" {value}" if value else ""
    print(f"[OK] {label}{suffix}")


def warn(label: str, value: object = "") -> None:
    suffix = f" {value}" if value else ""
    print(f"[WARN] {label}{suffix}")


def fail(label: str, value: object = "") -> None:
    suffix = f" {value}" if value else ""
    print(f"[FAIL] {label}{suffix}")


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    failed = 0
    print(f"Project: {ROOT}")
    print(f"Python: {sys.executable}")

    if (ROOT / ".env").exists():
        ok(".env exists")
    else:
        fail(".env missing", "copy .env.example to .env")
        failed += 1

    for module in ["fastapi", "uvicorn", "openai", "pydantic_settings", "requests"]:
        if module_exists(module):
            ok(f"python module {module}")
        else:
            fail(f"python module {module}")
            failed += 1

    for binary in ["ffmpeg", "ffprobe"]:
        path = shutil.which(binary)
        if path:
            ok(binary, path)
        else:
            fail(binary, "not found in PATH")
            failed += 1

    if os.environ.get("LLM_API_KEY", ""):
        ok("LLM_API_KEY visible in current environment")
    else:
        warn("LLM_API_KEY not visible in current process", "it may still be loaded from .env")

    cosy_python = THIRD_PARTY / "cosyvoice-env-win" / "python.exe"
    cosy_repo = THIRD_PARTY / "CosyVoice"
    model_dir = THIRD_PARTY / "models" / "Fun-CosyVoice3-0.5B"
    if cosy_python.exists():
        ok("CosyVoice Python", cosy_python)
    else:
        warn("CosyVoice Python missing", cosy_python)
    if cosy_repo.exists():
        ok("CosyVoice repo", cosy_repo)
    else:
        warn("CosyVoice repo missing", cosy_repo)
    if model_dir.exists():
        ok("Default CosyVoice model", model_dir)
    else:
        warn("Default CosyVoice model missing", model_dir)

    try:
        from app.main import app

        ok("backend import", bool(app))
    except Exception as exc:
        fail("backend import", exc)
        failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
