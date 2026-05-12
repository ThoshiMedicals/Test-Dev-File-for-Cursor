from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "news_ai_workers",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.tasks.ingest",
        "workers.tasks.nlp",
        "workers.tasks.recs",
        "workers.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

