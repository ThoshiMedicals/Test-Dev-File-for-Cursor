from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import auth_dep
from app.core.config import settings
from app.schemas.common import Envelope
from app.services.currents_api import currents_status
from app.services.newsapi import newsapi_status, validate_news_api_key

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])


class NewsSyncIn(BaseModel):
    country: str | None = Field(default=None, max_length=8)


@router.get("/news/validate", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def news_validate() -> Envelope[dict]:
    return Envelope(data=await validate_news_api_key())


@router.get("/news/status", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def news_status() -> Envelope[dict]:
    data = {
        **newsapi_status(),
        "currents": currents_status(),
        "scheduled_interval_minutes": settings.news_sync_interval_minutes,
    }
    return Envelope(data=data)


@router.get("/currents/status", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def currents_status_route() -> Envelope[dict]:
    return Envelope(data=currents_status())


@router.post("/news/sync", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def news_sync(payload: NewsSyncIn) -> Envelope[dict]:
    try:
        from workers.tasks.news_sync import sync_newsapi_headlines

        sync_newsapi_headlines.delay(payload.country)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Could not queue sync: {e}") from e
    return Envelope(data={"queued": True, "task": "news.sync_newsapi_headlines"})


@router.post("/news/sync-all", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def news_sync_all(payload: NewsSyncIn) -> Envelope[dict]:
    try:
        from workers.tasks.news_sync import sync_all_live_news

        sync_all_live_news.delay(payload.country)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Could not queue sync: {e}") from e
    return Envelope(data={"queued": True, "task": "news.sync_all_live_news"})


@router.post("/currents/sync", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def currents_sync() -> Envelope[dict]:
    try:
        from workers.tasks.news_sync import sync_currents_latest

        sync_currents_latest.delay()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Could not queue sync: {e}") from e
    return Envelope(data={"queued": True, "task": "news.sync_currents_latest"})
