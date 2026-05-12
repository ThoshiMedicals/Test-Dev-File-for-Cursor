from __future__ import annotations

from fastapi import APIRouter

from app.schemas.common import Envelope

router = APIRouter()


@router.get("/health", response_model=Envelope[dict])
async def health() -> Envelope[dict]:
    return Envelope(data={"ok": True})

