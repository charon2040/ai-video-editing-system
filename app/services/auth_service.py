from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

from app.core.db import app_db


DEFAULT_USER_ID = "local"
DEFAULT_USERNAME = "local"
DEFAULT_PASSWORD = "local123456"
SESSION_COOKIE_NAME = "clip_mvp_session"
SESSION_DAYS = 14


def _now() -> datetime:
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value or ""))
    except Exception:
        return datetime.min


class AuthService:
    def _normalize_username(self, username: str) -> str:
        normalized = str(username or "").strip().lower()
        if not re.fullmatch(r"[a-zA-Z0-9_.-]{3,32}", normalized):
            raise ValueError("用户名只能包含字母、数字、下划线、点和短横线，长度 3-32")
        return normalized

    def _validate_password(self, password: str) -> str:
        raw = str(password or "")
        if len(raw) < 6:
            raise ValueError("密码至少 6 位")
        if len(raw) > 128:
            raise ValueError("密码不能超过 128 位")
        return raw

    def _hash_password(self, password: str, salt: str | None = None) -> str:
        salt = salt or secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            180_000,
        ).hex()
        return f"pbkdf2_sha256${salt}${digest}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        parts = str(stored_hash or "").split("$")
        if len(parts) != 3 or parts[0] != "pbkdf2_sha256":
            return False
        expected = self._hash_password(password, parts[1])
        return hmac.compare_digest(expected, stored_hash)

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()

    def sanitize_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        if not user:
            return {}
        return {
            "id": str(user.get("id", "") or ""),
            "username": str(user.get("username", "") or ""),
            "display_name": str(user.get("display_name", "") or ""),
            "is_active": bool(user.get("is_active", True)),
            "created_at": str(user.get("created_at", "") or ""),
            "updated_at": str(user.get("updated_at", "") or ""),
        }

    def ensure_default_user(self) -> Dict[str, Any]:
        app_db.init_schema()
        user = app_db.get_user(DEFAULT_USER_ID)
        if user:
            return user
        now = _now_iso()
        return app_db.upsert_user(
            {
                "id": DEFAULT_USER_ID,
                "username": DEFAULT_USERNAME,
                "password_hash": self._hash_password(DEFAULT_PASSWORD),
                "display_name": "本地默认用户",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        )

    def register(self, *, username: str, password: str, display_name: str = "") -> Dict[str, Any]:
        normalized_username = self._normalize_username(username)
        raw_password = self._validate_password(password)
        if app_db.find_user_by_username(normalized_username):
            raise ValueError("用户名已存在")
        now = _now_iso()
        return app_db.upsert_user(
            {
                "id": f"user_{uuid.uuid4().hex[:12]}",
                "username": normalized_username,
                "password_hash": self._hash_password(raw_password),
                "display_name": str(display_name or normalized_username).strip()[:40],
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
        )

    def authenticate(self, *, username: str, password: str) -> Dict[str, Any]:
        normalized_username = self._normalize_username(username)
        user = app_db.find_user_by_username(normalized_username)
        if not user or not user.get("is_active"):
            raise ValueError("用户名或密码错误")
        if not self._verify_password(str(password or ""), str(user.get("password_hash", "") or "")):
            raise ValueError("用户名或密码错误")
        return user

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(40)
        now = _now()
        expires = now + timedelta(days=SESSION_DAYS)
        app_db.upsert_user_session(
            {
                "token_hash": self._hash_token(token),
                "user_id": str(user_id or ""),
                "created_at": now.isoformat(timespec="seconds"),
                "expires_at": expires.isoformat(timespec="seconds"),
                "last_seen_at": now.isoformat(timespec="seconds"),
            }
        )
        return token

    def get_user_by_session_token(self, token: str) -> Dict[str, Any]:
        token_hash = self._hash_token(token)
        session = app_db.get_user_session(token_hash)
        if not session:
            return {}
        if _parse_iso(str(session.get("expires_at", ""))) <= _now():
            app_db.delete_user_session(token_hash)
            return {}
        user = app_db.get_user(str(session.get("user_id", "") or ""))
        if not user or not user.get("is_active"):
            return {}
        now = _now_iso()
        app_db.upsert_user_session({**session, "last_seen_at": now})
        return user

    def delete_session(self, token: str) -> bool:
        return app_db.delete_user_session(self._hash_token(token))


auth_service = AuthService()
