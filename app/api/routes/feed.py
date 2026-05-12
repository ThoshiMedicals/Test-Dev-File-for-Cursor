from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import auth_dep, db_dep
from app.services.recs import recommend_for_user
from app.schemas.common import Envelope

router = APIRouter(prefix="/v1/feed", tags=["feed"])


@router.get("/personalized", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def personalized_feed(
    user_external_id: str,
    limit: int = 50,
    cursor: str | None = None,
    db: AsyncSession = Depends(db_dep),
) -> Envelope[list[dict]]:
    items, versions = await recommend_for_user(db, user_external_id=user_external_id, limit=limit)
    return Envelope(data=items, meta={"next_cursor": cursor, "model_versions": versions})  # type: ignore[arg-type]


@router.get("/updates", response_model=Envelope[list[dict]], dependencies=[Depends(auth_dep)])
async def feed_updates(since: str | None = None, limit: int = 50) -> Envelope[list[dict]]:
    # Implemented in ingestion todo; placeholder contract.
    return Envelope(data=[], meta={"next_cursor": None, "model_versions": {}})  # type: ignore[arg-type]

