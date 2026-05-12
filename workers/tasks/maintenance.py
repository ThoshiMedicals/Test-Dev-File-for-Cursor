from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy import delete

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.user import UserEvent


@shared_task(name="maintenance.purge_old_events")
def purge_old_events() -> dict:
    cutoff = datetime.utcnow() - timedelta(days=settings.retention_days_events)

    async def _run() -> dict:
        async with SessionLocal() as db:
            result = await db.execute(delete(UserEvent).where(UserEvent.created_at < cutoff))
            await db.commit()
            return {"purged": int(result.rowcount or 0), "cutoff": cutoff.isoformat()}

    return asyncio.run(_run())

