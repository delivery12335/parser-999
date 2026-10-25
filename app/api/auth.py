from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.config import Settings


def verify_android_token(settings: Settings, authorization: str | None = Header(default=None)) -> None:
    expected = f"Bearer {settings.android_api_token}"
    if not settings.android_api_token or not authorization or not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Android token")
