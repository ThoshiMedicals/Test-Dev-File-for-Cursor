from __future__ import annotations

import asyncio

from celery import shared_task

from app.core.config import settings
from app.core.db import SessionLocal
from app.schemas.fetched_article import FetchedArticle
from app.services.currents_api import fetch_currents_latest
from app.services.live_news_ingest import ingest_fetched_articles
from app.services.newsapi import fetch_top_headlines


@shared_task(name="news.sync_newsapi_headlines")
def sync_newsapi_headlines(country: str | None = None) -> dict:
    async def _run() -> dict:
        items = await fetch_top_headlines(country=country)
        async with SessionLocal() as db:
            return await ingest_fetched_articles(db, items)

    return asyncio.run(_run())


@shared_task(name="news.sync_currents_latest")
def sync_currents_latest() -> dict:
    async def _run() -> dict:
        items = await fetch_currents_latest()
        async with SessionLocal() as db:
            return await ingest_fetched_articles(db, items)

    return asyncio.run(_run())


@shared_task(name="news.sync_all_live_news")
def sync_all_live_news(country: str | None = None) -> dict:
    """Fetch from all configured providers, merge by URL, ingest once."""

    async def _run() -> dict:
        merged: dict[str, FetchedArticle] = {}
        errors: list[str] = []

        if settings.news_api_key:
            try:
                for it in await fetch_top_headlines(country=country):
                    merged[it.url] = it
            except Exception as e:  # noqa: BLE001
                errors.append(f"newsapi:{e!s}")

        if settings.currents_api_key:
            try:
                for it in await fetch_currents_latest():
                    merged.setdefault(it.url, it)
            except Exception as e:  # noqa: BLE001
                errors.append(f"currents:{e!s}")

        items = list(merged.values())
        if not items:
            return {
                "fetched": 0,
                "created": 0,
                "errors": errors,
                "message": "No articles fetched (missing API keys or upstream errors).",
            }

        async with SessionLocal() as db:
            stats = await ingest_fetched_articles(db, items)
        stats["errors"] = errors
        return stats

    return asyncio.run(_run())
