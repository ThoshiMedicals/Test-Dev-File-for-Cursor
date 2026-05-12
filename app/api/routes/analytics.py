from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import auth_dep, db_dep
from app.schemas.common import Envelope
from app.services.analytics import engagement_overview, top_articles
from app.services.http_cache import set_public_json_cache

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/overview", response_model=Envelope[dict], dependencies=[Depends(auth_dep)])
async def analytics_overview(
    response: Response,
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[dict]:
    data = await engagement_overview(db, days=days)
    set_public_json_cache(response)
    return Envelope(data=data)


@router.get("/articles/top", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def analytics_top_articles(
    response: Response,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    data = await top_articles(db, days=days, limit=limit)
    set_public_json_cache(response)
    return Envelope(data=data)
