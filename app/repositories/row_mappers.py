from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict


def row_to_task(row: sqlite3.Row | None) -> Dict[str, Any]:
    if row is None:
        return {}
    keys = set(row.keys())
    return {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in keys else "local",
        "project_id": row["project_id"] if "project_id" in keys else "default",
        "status": row["status"],
        "progress": row["progress"],
        "stage": row["stage"],
        "message": row["message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "payload": json.loads(row["payload_json"] or "{}"),
        "artifacts": json.loads(row["artifacts_json"] or "{}"),
        "result": json.loads(row["result_json"] or "{}"),
        "error": row["error"] or "",
        "source_path": row["source_path"] or "",
        "source_hash": row["source_hash"] or "",
        "source_size": int(row["source_size"] or 0),
    }


def row_to_task_event(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        detail = json.loads(row["detail_json"] or "{}")
    except Exception:
        detail = {}
    return {
        "id": int(row["id"] or 0),
        "task_id": row["task_id"],
        "event_type": row["event_type"] or "state_changed",
        "status": row["status"] or "",
        "stage": row["stage"] or "",
        "progress": int(row["progress"] or 0),
        "message": row["message"] or "",
        "detail": detail if isinstance(detail, dict) else {},
        "created_at": row["created_at"] or "",
    }


def row_to_voice_profile(row: sqlite3.Row | None) -> Dict[str, Any]:
    if row is None:
        return {}
    keys = set(row.keys())
    return {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in keys else "",
        "label": row["label"],
        "description": row["description"] or "",
        "prompt_text": row["prompt_text"] or "",
        "prompt_wav_path": row["prompt_wav_path"] or "",
        "language": row["language"] or "",
        "source_type": row["source_type"] or "seed",
        "is_default": bool(row["is_default"]),
        "is_active": bool(row["is_active"]),
        "sort_order": int(row["sort_order"] or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_project_knowledge(row: sqlite3.Row | None) -> Dict[str, Any]:
    if row is None:
        return {
            "id": "default",
            "user_id": "local",
            "project_id": "default",
            "title": "项目知识库",
            "content": "",
            "created_at": "",
            "updated_at": "",
        }
    keys = set(row.keys())
    return {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in keys else "local",
        "project_id": row["project_id"] if "project_id" in keys else "default",
        "title": row["title"] or "项目知识库",
        "content": row["content"] or "",
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def row_to_project(row: sqlite3.Row | None) -> Dict[str, Any]:
    if row is None:
        return {}
    keys = set(row.keys())
    return {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in keys else "local",
        "title": row["title"] or "默认项目",
        "description": row["description"] or "",
        "default_knowledge_base_id": row["default_knowledge_base_id"] or "default",
        "default_pipeline_mode": row["default_pipeline_mode"] or "narration_clip",
        "default_knowledge_policy": row["default_knowledge_policy"] if "default_knowledge_policy" in keys else "none",
        "default_duration_seconds": int(row["default_duration_seconds"] or 0) if "default_duration_seconds" in keys else 0,
        "default_style": row["default_style"] if "default_style" in keys else "summary",
        "default_enable_dubbing": bool(row["default_enable_dubbing"]) if "default_enable_dubbing" in keys else False,
        "default_voice_mode": row["default_voice_mode"] if "default_voice_mode" in keys else "standard",
        "default_voice_profile_id": row["default_voice_profile_id"] if "default_voice_profile_id" in keys else "",
        "default_tts_speed": float(row["default_tts_speed"] or 1.0) if "default_tts_speed" in keys else 1.0,
        "default_keep_original_audio": bool(row["default_keep_original_audio"]) if "default_keep_original_audio" in keys else True,
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def row_to_clip_plan(row: sqlite3.Row) -> Dict[str, Any]:
    keys = set(row.keys())
    return {
        "id": row["id"],
        "user_id": row["user_id"] if "user_id" in keys else "local",
        "task_id": row["task_id"],
        "source_hash": row["source_hash"],
        "request_text": row["request_text"],
        "request_mode": row["request_mode"],
        "duration_seconds": int(row["duration_seconds"] or 0),
        "style": row["style"] or "",
        "script": row["script"] or "",
        "suggestions": json.loads(row["suggestions_json"] or "[]"),
        "segments": json.loads(row["segments_json"] or "[]"),
        "plan_mode": row["plan_mode"] or "",
        "total_duration_ms": int(row["total_duration_ms"] or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_asr_cache(row: sqlite3.Row | None) -> Dict[str, Any]:
    if row is None:
        return {}
    return {
        "source_hash": row["source_hash"],
        "original_filename": row["original_filename"],
        "source_size": int(row["source_size"] or 0),
        "audio_path": row["audio_path"],
        "subtitles": json.loads(row["subtitles_json"] or "[]"),
        "subtitle_count": int(row["subtitle_count"] or 0),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def row_to_user(row: sqlite3.Row | None) -> Dict[str, Any]:
    if row is None:
        return {}
    return {
        "id": row["id"],
        "username": row["username"] or "",
        "password_hash": row["password_hash"] or "",
        "display_name": row["display_name"] or "",
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"] or "",
        "updated_at": row["updated_at"] or "",
    }


def row_to_user_session(row: sqlite3.Row | None) -> Dict[str, Any]:
    if row is None:
        return {}
    return {
        "token_hash": row["token_hash"] or "",
        "user_id": row["user_id"] or "",
        "created_at": row["created_at"] or "",
        "expires_at": row["expires_at"] or "",
        "last_seen_at": row["last_seen_at"] or "",
    }
