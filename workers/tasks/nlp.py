from __future__ import annotations

import asyncio

from celery import shared_task

from app.core.db import SessionLocal
from app.services.nlp import enrich_article as enrich_article_impl


@shared_task(name="nlp.enqueue_enrich_article")
def enqueue_enrich_article(article_id: str) -> dict:
    enrich_article.delay(article_id)
    return {"enqueued": True, "article_id": article_id}


@shared_task(name="nlp.enrich_article")
def enrich_article(article_id: str) -> dict:
    async def _run() -> dict:
        async with SessionLocal() as db:
            versions = await enrich_article_impl(db, article_id=article_id)
            return {"article_id": article_id, "status": "enriched", "model_versions": versions}

    return asyncio.run(_run())

