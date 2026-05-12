from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime

from celery import shared_task
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.article import Article, Source
from app.services.newsapi import fetch_top_headlines
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


@shared_task(name="news.sync_newsapi_headlines")
def sync_newsapi_headlines(country: str | None = None) -> dict:
    async def _run() -> dict:
        items = await fetch_top_headlines(country=country)
        created = 0
        async with SessionLocal() as db:
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
                    ingested_at=datetime.utcnow(),
                    source=source_obj,
                    image_url=it.image_url,
                )
                db.add(article)
                await db.commit()
                await db.refresh(article)
                enrich_article.delay(str(article.id))
                created += 1
        return {"fetched": len(items), "created": created}

    return asyncio.run(_run())
