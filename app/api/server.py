from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.api.auth import verify_android_token
from app.config import Settings
from app.database.repository import Repository


class CallCommand(BaseModel):
    request_id: str
    phone: str


class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(dialing|completed|failed|rejected)$")
    message: str | None = Field(default=None, max_length=500)


def create_api(settings: Settings, repository: Repository) -> FastAPI:
    app = FastAPI(title="999 Apartment Watcher Android API", docs_url=None, redoc_url=None)

    async def require_android(authorization: str | None = Header(default=None)) -> None:
        verify_android_token(settings, authorization)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/android/commands/next", response_model=CallCommand | None, dependencies=[Depends(require_android)])
    async def next_command() -> CallCommand | None:
        call = await repository.claim_next_call()
        return CallCommand(request_id=call.request_id, phone=call.phone) if call else None

    @app.post("/api/android/commands/{request_id}/status", dependencies=[Depends(require_android)])
    async def call_status(request_id: str, payload: StatusUpdate) -> dict[str, bool]:
        try:
            updated = await repository.update_call_status(request_id, payload.status, payload.message)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if not updated:
            raise HTTPException(status_code=409, detail="Command already finalized or unknown")
        return {"updated": True}

    return app
