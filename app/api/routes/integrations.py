from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import auth_dep
from app.schemas.common import Envelope
from app.services.newsapi import newsapi_status

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])


class NewsSyncIn(BaseModel):
    country: str | None = Field(default=None, max_length=8)


@router.get("/news/status", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def news_status() -> Envelope[dict]:
    return Envelope(data=newsapi_status())


@router.post("/news/sync", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def news_sync(payload: NewsSyncIn) -> Envelope[dict]:
    try:
        from workers.tasks.news_sync import sync_newsapi_headlines

        sync_newsapi_headlines.delay(payload.country)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Could not queue sync: {e}") from e
    return Envelope(data={"queued": True, "task": "news.sync_newsapi_headlines"})
