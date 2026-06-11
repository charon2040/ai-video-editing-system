from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException, Request, status

from app.services.auth_service import SESSION_COOKIE_NAME, auth_service


def optional_current_user(request: Request) -> Dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not token:
        return {}
    user = auth_service.get_user_by_session_token(token)
    return auth_service.sanitize_user(user) if user else {}


def get_current_user(request: Request) -> Dict[str, Any]:
    user = optional_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请先登录",
        )
    return user


def current_user_id(user: Dict[str, Any]) -> str:
    return str(user.get("id", "") or "").strip()
