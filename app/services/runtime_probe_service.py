from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any, Dict


class RuntimeProbeService:
    def module_available(self, module_name: str) -> bool:
        return importlib.util.find_spec(module_name) is not None

    def probe_external_python(self, python_path: Path, modules: list[str]) -> Dict[str, Any]:
        if not python_path.exists():
            return {
                "python": str(python_path),
                "exists": False,
                "modules": {module: False for module in modules},
                "error": "python_not_found",
            }

        code = (
            "import importlib.util, json, sys; "
            "mods = sys.argv[1:]; "
            "print(json.dumps({"
            "'python': sys.executable, "
            "'exists': True, "
            "'modules': {m: importlib.util.find_spec(m) is not None for m in mods}"
            "}, ensure_ascii=False))"
        )
        try:
            result = subprocess.run(
                [str(python_path), "-c", code, *modules],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            return json.loads((result.stdout or "").strip() or "{}")
        except Exception as exc:
            return {
                "python": str(python_path),
                "exists": True,
                "modules": {module: False for module in modules},
                "error": str(exc),
            }


runtime_probe_service = RuntimeProbeService()
