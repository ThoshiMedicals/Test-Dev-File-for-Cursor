from __future__ import annotations

from datetime import datetime

from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import auth_dep, db_dep
from app.core.config import settings
from app.schemas.common import Envelope, EnvelopeMeta
from app.services.feed_intel import breaking_articles, feed_since, trending_articles
from app.services.recs import recommend_for_user

router = APIRouter(prefix="/v1/feed", tags=["feed"])


def _cache(response: Response) -> None:
    response.headers["Cache-Control"] = (
        f"public, max-age={settings.api_cache_control_seconds}, stale-while-revalidate=120"
    )


@router.get("/personalized", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def personalized_feed(
    response: Response,
    user_external_id: str,
    limit: int = 50,
    cursor: str | None = None,
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    items, versions = await recommend_for_user(db, user_external_id=user_external_id, limit=limit)
    _cache(response)
    return Envelope(data=items, meta=EnvelopeMeta(next_cursor=cursor, model_versions=versions))


@router.get("/updates", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def feed_updates(
    response: Response,
    since: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    since_dt: datetime | None = None
    if since:
        try:
            since_dt = date_parser.isoparse(since)
        except (ValueError, TypeError) as e:
            raise HTTPException(status_code=400, detail="Invalid `since` ISO-8601 datetime.") from e
    data = await feed_since(db, since=since_dt, limit=limit)
    _cache(response)
    return Envelope(data=data, meta=EnvelopeMeta(next_cursor=None, model_versions={}))


@router.get("/trending", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def feed_trending(
    response: Response,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    data = await trending_articles(db, limit=limit)
    _cache(response)
    return Envelope(data=data, meta=EnvelopeMeta(model_versions={"ranking": "engagement_v1"}))


@router.get("/breaking", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def feed_breaking(
    response: Response,
    limit: int = Query(15, ge=1, le=50),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    data = await breaking_articles(db, limit=limit)
    _cache(response)
    return Envelope(data=data, meta=EnvelopeMeta(model_versions={"ranking": "burst_v1"}))
