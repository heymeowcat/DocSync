"""GitHub OAuth authentication routes."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import jwt
import requests
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


def get_current_user(request: Request) -> dict:
    """Resolve the authenticated user from the JWT cookie."""
    token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    return payload


@router.get("/auth/github")
async def github_login():
    if not settings.github_client_id:
        raise HTTPException(status_code=503, detail="GitHub OAuth is not configured")
    return RedirectResponse(
        f"https://github.com/login/oauth/authorize?client_id={settings.github_client_id}&scope=repo"
    )


@router.get("/auth/github/callback")
async def github_callback(code: str, response: Response):
    token_response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": settings.github_client_id,
            "client_secret": settings.github_client_secret,
            "code": code,
        },
        timeout=30,
    )
    token_response.raise_for_status()
    access_token = token_response.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to get access token")

    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    user_response.raise_for_status()
    user_data = user_response.json()

    token = jwt.encode(
        {
            "sub": str(user_data["id"]),
            "name": user_data.get("login", ""),
            "access_token": access_token,
            "exp": datetime.utcnow() + timedelta(days=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    redirect = RedirectResponse(url="/dashboard")
    redirect.set_cookie(key="token", value=token, httponly=True, samesite="lax")
    return redirect
