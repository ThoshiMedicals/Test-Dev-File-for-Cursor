from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.article import Article
from app.services.feed_intel import article_to_card


async def related_by_co_engagement(
    db: AsyncSession,
    *,
    article_id: uuid.UUID,
    limit: int = 8,
    days: int = 45,
) -> list[dict]:
    """
    Collaborative-style related articles: other pieces frequently engaged with
    by users who also engaged with the seed article (implicit co-occurrence).
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    sql = text(
        """
        SELECT e.article_id::text AS aid, COUNT(*) AS cnt
        FROM user_events e
        WHERE e.created_at >= :since
          AND e.article_id <> :seed
          AND e.event_type IN ('click', 'save', 'share', 'dwell', 'view', 'like', 'comment')
          AND e.user_external_id IN (
            SELECT DISTINCT user_external_id
            FROM user_events
            WHERE article_id = :seed
              AND created_at >= :since
              AND event_type IN ('click', 'save', 'share', 'dwell', 'view', 'like', 'comment')
          )
        GROUP BY e.article_id
        ORDER BY cnt DESC
        LIMIT :lim
        """
    )
    rows = (await db.execute(sql, {"since": since, "seed": article_id, "lim": limit})).mappings().all()
    if not rows:
        return []
    ids = [uuid.UUID(r["aid"]) for r in rows]
    articles = (
        await db.execute(
            select(Article)
            .options(selectinload(Article.category_primary), selectinload(Article.source))
            .where(Article.id.in_(ids))
        )
    ).scalars().all()
    by_id = {a.id: a for a in articles}
    ordered: list[Article] = []
    for r in rows:
        aid = uuid.UUID(r["aid"])
        if aid in by_id:
            ordered.append(by_id[aid])
    cnt_by_id = {uuid.UUID(r["aid"]): float(r["cnt"]) for r in rows}
    return [article_to_card(a, related_score=cnt_by_id.get(a.id, 0.0)) for a in ordered]
