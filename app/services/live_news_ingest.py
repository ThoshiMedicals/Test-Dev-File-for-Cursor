from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article, Source
from app.schemas.fetched_article import FetchedArticle
from workers.tasks.nlp import enrich_article


def _hash_article(url: str, title: str, body_text: str | None) -> str:
    h = hashlib.sha256()
    h.update(url.encode("utf-8"))
    h.update(b"\n")
    h.update(title.encode("utf-8"))
    if body_text:
        h.update(b"\n")
        h.update(body_text.encode("utf-8"))
    return h.hexdigest()


async def ingest_fetched_articles(db: AsyncSession, items: list[FetchedArticle]) -> dict[str, Any]:
    """Insert new articles from normalized provider rows; queue NLP enrichment."""
    created = 0
    for it in items:
        existing = (await db.execute(select(Article).where(Article.url == it.url))).scalar_one_or_none()
        if existing:
            continue
        raw_hash = _hash_article(it.url, it.title, it.lead_text)
        dup = (await db.execute(select(Article).where(Article.raw_hash == raw_hash))).scalar_one_or_none()
        if dup:
            continue
        source_obj = None
        if it.source_name:
            source_obj = (await db.execute(select(Source).where(Source.name == it.source_name))).scalar_one_or_none()
            if source_obj is None:
                source_obj = Source(name=it.source_name)
                db.add(source_obj)
                await db.flush()
        article = Article(
            url=it.url,
            raw_hash=raw_hash,
            title=it.title,
            lead_text=it.lead_text,
            body_text=None,
            author=it.author,
            published_at=it.published_at,
            ingested_at=datetime.now(timezone.utc),
            source=source_obj,
            image_url=it.image_url,
        )
        db.add(article)
        await db.commit()
        await db.refresh(article)
        enrich_article.delay(str(article.id))
        created += 1
    return {"fetched": len(items), "created": created}
