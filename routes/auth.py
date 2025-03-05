from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
import requests
import jwt
from datetime import datetime, timedelta
from config import settings

router = APIRouter()

@router.get("/auth/github")
async def github_login():
    return RedirectResponse(
        f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&scope=repo"
    )

@router.get("/auth/github/callback")
async def github_callback(code: str):
    # Exchange code for access token
    response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        data={
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
        },
    )
    
    access_token = response.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to get access token")
    
    # Get user info
    user_response = requests.get(
        "https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_data = user_response.json()
    
    # Create JWT
    token = jwt.encode(
        {
            "sub": str(user_data["id"]),
            "name": user_data["login"],
            "access_token": access_token,
            "exp": datetime.utcnow() + timedelta(days=1)
        },
        settings.JWT_SECRET,
        algorithm="HS256"
    )
    
    response = RedirectResponse(url="/dashboard")
    response.set_cookie(key="token", value=token, httponly=True)
    return response