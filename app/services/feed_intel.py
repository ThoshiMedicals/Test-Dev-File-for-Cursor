from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.article import Article
from app.models.user import UserEvent


async def _engagement_map(db: AsyncSession, *, hours: int) -> dict[str, dict[str, float]]:
    """Per-article engagement in the last `hours` hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        await db.execute(
            select(
                UserEvent.article_id,
                UserEvent.event_type,
                func.count(UserEvent.id),
                func.coalesce(func.sum(UserEvent.value), 0.0),
            )
            .where(UserEvent.created_at >= since)
            .where(UserEvent.event_type.in_(["click", "share", "dwell", "comment"]))
            .group_by(UserEvent.article_id, UserEvent.event_type)
        )
    ).all()

    m: dict[str, dict[str, float]] = {}
    for aid, et, cnt, val_sum in rows:
        key = str(aid)
        if key not in m:
            m[key] = {"click": 0.0, "share": 0.0, "dwell": 0.0, "comment": 0.0}
        if et == "click":
            m[key]["click"] += float(cnt or 0)
        elif et == "share":
            m[key]["share"] += float(cnt or 0)
        elif et == "dwell":
            m[key]["dwell"] += float(val_sum or 0.0) + 0.1 * float(cnt or 0)
        elif et == "comment":
            m[key]["comment"] += float(cnt or 0)
    return m


async def engagement_hotness(db: AsyncSession, *, hours: int = 24) -> dict[str, float]:
    em = await _engagement_map(db, hours=hours)
    return {
        aid: e["click"] + 3.0 * e["share"] + 0.02 * e["dwell"] + 2.0 * e["comment"]
        for aid, e in em.items()
    }


def _trending_score(eng: dict[str, float], hours_since_publish: float) -> float:
    clicks = eng.get("click", 0.0)
    shares = eng.get("share", 0.0) * 3.0
    dwell = eng.get("dwell", 0.0) * 0.02
    comments = eng.get("comment", 0.0) * 2.0
    recency = 1.0 / (1.0 + max(0.0, hours_since_publish) / 12.0)
    return (clicks + shares + dwell + comments + 0.01) * recency


async def trending_articles(db: AsyncSession, *, limit: int = 20) -> list[dict]:
    eng = await _engagement_map(db, hours=24)
    rows = (
        await db.execute(
            select(Article)
            .options(selectinload(Article.category_primary))
            .where(Article.published_at >= datetime.now(timezone.utc) - timedelta(days=3))
            .order_by(Article.published_at.desc().nullslast())
            .limit(400)
        )
    ).scalars().all()

    scored: list[tuple[float, Article]] = []
    now = datetime.now(timezone.utc)
    for a in rows:
        hp = 999.0
        if a.published_at:
            pt = a.published_at if a.published_at.tzinfo else a.published_at.replace(tzinfo=timezone.utc)
            hp = max(0.0, (now - pt).total_seconds() / 3600.0)
        e = eng.get(str(a.id), {})
        scored.append((_trending_score(e, hp), a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [article_to_card(a, trending_score=float(s)) for (s, a) in scored[:limit]]


async def breaking_articles(db: AsyncSession, *, limit: int = 15) -> list[dict]:
    """High short-window engagement + very recent publish."""
    eng = await _engagement_map(db, hours=2)
    rows = (
        await db.execute(
            select(Article)
            .options(selectinload(Article.category_primary))
            .where(Article.published_at >= datetime.now(timezone.utc) - timedelta(hours=18))
            .order_by(Article.published_at.desc().nullslast())
            .limit(200)
        )
    ).scalars().all()

    now = datetime.now(timezone.utc)
    scored: list[tuple[float, Article]] = []
    for a in rows:
        e = eng.get(str(a.id), {})
        burst = e.get("click", 0.0) + e.get("share", 0.0) * 4.0
        hp = 999.0
        if a.published_at:
            pt = a.published_at if a.published_at.tzinfo else a.published_at.replace(tzinfo=timezone.utc)
            hp = max(0.0, (now - pt).total_seconds() / 3600.0)
        freshness = 1.0 / (1.0 + hp / 3.0)
        scored.append((burst * freshness + 0.01 * burst, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [article_to_card(a, breaking_score=float(s)) for (s, a) in scored[:limit]]


async def feed_since(db: AsyncSession, *, since: datetime | None, limit: int = 50) -> list[dict]:
    base = select(Article).options(selectinload(Article.category_primary))
    if since is not None:
        q = base.where(Article.ingested_at > since).order_by(Article.ingested_at.desc()).limit(limit)
    else:
        q = base.order_by(Article.published_at.desc().nullslast(), Article.ingested_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [article_to_card(a) for a in rows]


def article_to_card(a: Article, **scores: float) -> dict:
    from app.services.share_links import share_links_for_url

    card = {
        "article_id": str(a.id),
        "url": a.url,
        "title": a.title,
        "image_url": a.image_url,
        "summary_short": a.summary_short,
        "summary_long": a.summary_long,
        "category_primary": a.category_primary.slug if a.category_primary else None,
        "sentiment_label": a.sentiment_label,
        "sentiment_score": a.sentiment_score,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "source": a.source.name if a.source else None,
        "share_links": share_links_for_url(a.url, a.title),
    }
    card.update(scores)
    return card
