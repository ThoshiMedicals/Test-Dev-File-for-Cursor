from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.article import Article
from app.models.user import UserEvent


async def engagement_overview(db: AsyncSession, *, days: int = 7) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    by_type = (
        await db.execute(
            select(UserEvent.event_type, func.count(UserEvent.id))
            .where(UserEvent.created_at >= since)
            .group_by(UserEvent.event_type)
        )
    ).all()
    dau = (
        await db.execute(
            select(func.count(func.distinct(UserEvent.user_external_id))).where(UserEvent.created_at >= since)
        )
    ).scalar_one()
    return {
        "window_days": days,
        "since": since.isoformat(),
        "distinct_users_with_events": int(dau or 0),
        "events_by_type": {str(et): int(c or 0) for et, c in by_type},
    }


async def top_articles(db: AsyncSession, *, days: int = 7, limit: int = 20) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    weight = func.case(
        (UserEvent.event_type == "click", 1.0),
        (UserEvent.event_type == "view", 0.25),
        (UserEvent.event_type == "like", 2.0),
        (UserEvent.event_type == "save", 2.5),
        (UserEvent.event_type == "share", 3.0),
        (UserEvent.event_type == "comment", 3.5),
        (UserEvent.event_type == "dwell", func.coalesce(UserEvent.value, 0.0) * 0.05 + 0.1),
        else_=0.0,
    )
    rows = (
        await db.execute(
            select(UserEvent.article_id, func.sum(weight).label("score"), func.count(UserEvent.id).label("cnt"))
            .where(UserEvent.created_at >= since)
            .group_by(UserEvent.article_id)
            .order_by(func.sum(weight).desc())
            .limit(limit)
        )
    ).all()
    if not rows:
        return []
    ids = [r[0] for r in rows]
    articles = (
        await db.execute(select(Article).options(selectinload(Article.category_primary)).where(Article.id.in_(ids)))
    ).scalars().all()
    by_id = {a.id: a for a in articles}
    score_by_id = {r[0]: (float(r[1] or 0.0), int(r[2] or 0)) for r in rows}
    out: list[dict[str, Any]] = []
    for aid in ids:
        a = by_id.get(aid)
        if not a:
            continue
        sc, cnt = score_by_id[aid]
        out.append(
            {
                "article_id": str(aid),
                "title": a.title,
                "url": a.url,
                "category_primary": a.category_primary.slug if a.category_primary else None,
                "engagement_score": sc,
                "event_count": cnt,
            }
        )
    return out
