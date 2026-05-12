from __future__ import annotations

import asyncio
import uuid

from celery import shared_task
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.waitlist import WaitlistSubscriber
from app.services.waitlist_ai import summarize_personalization


@shared_task(name="waitlist.enrich_subscriber")
def enrich_waitlist_subscriber(subscriber_id: str) -> dict:
    async def _run() -> dict:
        async with SessionLocal() as db:
            sub = (
                await db.execute(select(WaitlistSubscriber).where(WaitlistSubscriber.id == uuid.UUID(subscriber_id)))
            ).scalar_one_or_none()
            if sub is None:
                return {"ok": False, "reason": "not_found"}
            summary, model = await summarize_personalization(
                interests=sub.interests or [],
                optional_feedback=sub.optional_feedback,
            )
            if summary:
                sub.ai_personalized_summary = summary
                sub.ai_model_version = model
                await db.commit()
            return {"ok": True, "updated": bool(summary)}

    return asyncio.run(_run())
