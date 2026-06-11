from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.api.auth_dependencies import optional_current_user
from app.core.config import settings
from app.domain.schemas import AuthCredentials
from app.services.auth_service import SESSION_COOKIE_NAME, SESSION_DAYS, auth_service
from app.services.project_service import project_service


router = APIRouter(prefix=settings.api_prefix)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, httponly=True, samesite="lax")


@router.get("/auth/me")
async def get_me(user=Depends(optional_current_user)):
    return {"authenticated": bool(user), "user": user or None}


@router.post("/auth/login")
async def login(payload: AuthCredentials, response: Response):
    try:
        user = auth_service.authenticate(
            username=payload.username,
            password=payload.password,
        )
        token = auth_service.create_session(str(user.get("id", "") or ""))
        _set_session_cookie(response, token)
        project_service.ensure_default_project(str(user.get("id", "") or "local"))
        return {"authenticated": True, "user": auth_service.sanitize_user(user)}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/auth/register")
async def register(payload: AuthCredentials, response: Response):
    try:
        user = auth_service.register(
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
        )
        project_service.ensure_default_project(str(user.get("id", "") or "local"))
        token = auth_service.create_session(str(user.get("id", "") or ""))
        _set_session_cookie(response, token)
        return {"authenticated": True, "user": auth_service.sanitize_user(user)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE_NAME, "")
    if token:
        auth_service.delete_session(token)
    _clear_session_cookie(response)
    return {"authenticated": False}
