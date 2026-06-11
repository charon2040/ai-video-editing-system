from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.task_service import task_service


def _compact_task(task: Dict[str, Any]) -> str:
    return " ".join(
        [
            str(task.get("id", "")),
            str(task.get("status", "")),
            str(task.get("stage", "")),
            f"{int(task.get('progress', 0) or 0)}%",
            str(task.get("message", "")),
        ]
    )


def _wait_task(task_id: str, *, stop_at_review: bool) -> Dict[str, Any]:
    last = ""
    while True:
        task = task_service.get_task(task_id)
        if not task:
            raise SystemExit(f"Task not found: {task_id}")
        line = _compact_task(task)
        if line != last:
            print(line, flush=True)
            last = line
        status = str(task.get("status", "") or "")
        if status in {"failed", "completed"}:
            return task
        if stop_at_review and status == "waiting_review":
            return task
        time.sleep(2)


def _print_draft(task: Dict[str, Any]) -> None:
    result = task.get("result", {}) or {}
    beats = result.get("draft_beats", []) or []
    print("\n=== DRAFT_SCRIPT ===")
    print(str(result.get("draft_script", "") or "").strip())
    print("\n=== DRAFT_BEATS ===")
    for beat in beats:
        print(f"{beat.get('order', '')}. {beat.get('title', '')}: {beat.get('text', '')}")
    print("\n=== GROUNDING ===")
    print(json.dumps(result.get("grounding", {}) or {}, ensure_ascii=False, indent=2))
    suggestions = result.get("suggestions", []) or []
    if suggestions:
        print("\n=== SUGGESTIONS ===")
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))


def _print_final(task: Dict[str, Any]) -> None:
    result = task.get("result", {}) or {}
    print("\n=== FINAL ===")
    print(
        json.dumps(
            {
                "id": task.get("id"),
                "status": task.get("status"),
                "stage": task.get("stage"),
                "error": task.get("error", ""),
                "selection_strategy": result.get("selection_strategy"),
                "segment_count": result.get("segment_count"),
                "actual_duration_ms": result.get("actual_duration_ms"),
                "voiceover_duration_ms": result.get("voiceover_duration_ms"),
                "artifacts": task.get("artifacts", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-task", required=True)
    parser.add_argument("--knowledge-base-id", default="default")
    parser.add_argument("--project-context", default="")
    parser.add_argument("--requirements", default="")
    parser.add_argument("--style", default="")
    parser.add_argument("--duration-seconds", type=int, default=-1)
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()

    base_task = task_service.get_task(args.base_task)
    if not base_task:
        raise SystemExit(f"Base task not found: {args.base_task}")
    payload = base_task.get("payload", {}) or {}

    task = task_service.create_task_from_existing_source(
        base_task_id=args.base_task,
        request_text=args.requirements or str(payload.get("request_text", "") or ""),
        request_mode=str(payload.get("request_mode", "") or "requirements"),
        project_context=args.project_context,
        knowledge_base_id=args.knowledge_base_id,
        duration_seconds=(
            int(args.duration_seconds)
            if int(args.duration_seconds) >= 0
            else int(payload.get("duration_seconds", 0) or 0)
        ),
        style=args.style or str(payload.get("style", "") or "summary"),
        enable_dubbing=bool(payload.get("enable_dubbing", False)),
        voice_profile_id=str(payload.get("voice_profile_id", "") or ""),
        tts_voice=str(payload.get("tts_voice", "") or ""),
        tts_speed=float(payload.get("tts_speed", 1.0) or 1.0),
        keep_original_audio=bool(payload.get("keep_original_audio", True)),
    )
    task_id = str(task.get("id", ""))
    print(f"created task: {task_id}", flush=True)

    task = _wait_task(task_id, stop_at_review=not args.approve)
    if str(task.get("status", "") or "") == "waiting_review":
        _print_draft(task)
        if args.approve:
            result = task.get("result", {}) or {}
            task_service.approve_draft(
                task_id,
                draft_script=str(result.get("draft_script", "") or ""),
                draft_beats=result.get("draft_beats", []) or [],
            )
            task = _wait_task(task_id, stop_at_review=False)

    if str(task.get("status", "") or "") in {"completed", "failed"}:
        _print_final(task)
    return 0 if str(task.get("status", "") or "") in {"waiting_review", "completed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
