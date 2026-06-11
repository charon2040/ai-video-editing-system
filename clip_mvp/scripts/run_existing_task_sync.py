from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.task_service import task_service


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task_id")
    args = parser.parse_args()

    task_id = str(args.task_id or "").strip()
    if not task_id:
        raise SystemExit("Missing task_id")

    task = task_service.get_task(task_id)
    if not task:
        raise SystemExit(f"Task not found: {task_id}")

    status = str(task.get("status", "") or "")
    if status in {"queued", "running"}:
        print(f"[sync] running draft for {task_id}", flush=True)
        task_service._run_task(task_id, phase="draft")
        task = task_service.get_task(task_id)

    if str(task.get("status", "") or "") == "waiting_review":
        result = task.get("result", {}) or {}
        beats = task_service._normalize_draft_beats(result.get("draft_beats", []))
        script = str(result.get("draft_script", "") or "").strip()
        if not beats:
            raise SystemExit("Draft generated no beats")
        if not script:
            script = task_service._build_script_from_beats(beats)

        print(f"[sync] approving draft for {task_id}: beats={len(beats)}", flush=True)
        task_service.update_task(
            task_id,
            status="queued",
            stage="queued",
            progress=72,
            message="文案已确认，准备继续配音与选片",
            error="",
            result={
                "draft_script": script,
                "draft_beats": beats,
                "review_status": "approved",
                "script": script,
                "voiceover_script": task_service._build_script_from_beats(beats),
            },
        )

        print(f"[sync] running finalize for {task_id}", flush=True)
        task_service._run_task(task_id, phase="finalize")

    final_task = task_service.get_task(task_id)
    result = final_task.get("result", {}) or {}
    print(
        "[sync] final",
        final_task.get("id"),
        final_task.get("status"),
        final_task.get("stage"),
        final_task.get("progress"),
        result.get("selection_strategy"),
        result.get("segment_count"),
        result.get("actual_duration_ms"),
        final_task.get("error", ""),
        flush=True,
    )
    return 0 if final_task.get("status") == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
