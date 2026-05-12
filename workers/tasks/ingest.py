from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime

import feedparser
import httpx
from bs4 import BeautifulSoup
from celery import shared_task
from readability import Document
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.article import Article, Source
from workers.tasks.nlp import enqueue_enrich_article


def _hash_article(url: str, title: str, body_text: str | None) -> str:
    h = hashlib.sha256()
    h.update(url.encode("utf-8"))
    h.update(b"\n")
    h.update(title.encode("utf-8"))
    if body_text:
        h.update(b"\n")
        h.update(body_text.encode("utf-8"))
    return h.hexdigest()


async def _fetch_and_extract(url: str) -> tuple[str | None, str | None]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
        html = r.text

    doc = Document(html)
    content_html = doc.summary(html_partial=True)
    title = doc.short_title()

    soup = BeautifulSoup(content_html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lead = None
    if text:
        lead = "\n".join(text.splitlines()[:3]).strip() or None
    return title or None, text or None


async def _ingest_one(url: str, title_hint: str | None, source_name: str | None, published_at: datetime | None) -> str | None:
    async with SessionLocal() as db:
        existing = (await db.execute(select(Article).where(Article.url == url))).scalar_one_or_none()
        if existing:
            return str(existing.id)

        extracted_title, body_text = await _fetch_and_extract(url)
        title = extracted_title or title_hint or url
        raw_hash = _hash_article(url=url, title=title, body_text=body_text)

        # Dedup by hash if same story comes through different URL variants.
        dup = (await db.execute(select(Article).where(Article.raw_hash == raw_hash))).scalar_one_or_none()
        if dup:
            return str(dup.id)

        source_obj = None
        if source_name:
            source_obj = (await db.execute(select(Source).where(Source.name == source_name))).scalar_one_or_none()
            if source_obj is None:
                source_obj = Source(name=source_name)
                db.add(source_obj)

        article = Article(
            url=url,
            raw_hash=raw_hash,
            title=title,
            body_text=body_text,
            lead_text=(body_text.split("\n", 1)[0] if body_text else None),
            published_at=published_at,
            ingested_at=datetime.utcnow(),
            source=source_obj,
        )
        db.add(article)
        await db.commit()
        await db.refresh(article)
        return str(article.id)


@shared_task(name="ingest.rss_poll")
def rss_poll(feed_url: str, source_name: str | None = None, max_entries: int = 25) -> dict:
    parsed = feedparser.parse(feed_url)
    entries = parsed.entries[:max_entries]

    async def _run() -> dict:
        ingested: list[str] = []
        for e in entries:
            url = getattr(e, "link", None)
            if not url:
                continue
            title_hint = getattr(e, "title", None)
            published_parsed = getattr(e, "published_parsed", None)
            published_at = datetime(*published_parsed[:6]) if published_parsed else None
            article_id = await _ingest_one(url=url, title_hint=title_hint, source_name=source_name, published_at=published_at)
            if article_id:
                ingested.append(article_id)
                enqueue_enrich_article.delay(article_id)
        return {"feed_url": feed_url, "ingested_count": len(ingested), "article_ids": ingested}

    return asyncio.run(_run())

