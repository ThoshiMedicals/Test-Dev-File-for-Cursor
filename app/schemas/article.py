from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import AnyHttpUrl, BaseModel, Field


class ArticleIn(BaseModel):
    url: AnyHttpUrl
    title: str
    body_text: str | None = None
    lead_text: str | None = None
    author: str | None = None
    source: str | None = None
    published_at: datetime | None = None
    language: str | None = None


class ArticleOut(BaseModel):
    id: uuid.UUID
    url: AnyHttpUrl
    title: str
    author: str | None
    source: str | None
    published_at: datetime | None
    ingested_at: datetime
    language: str | None

    category_primary: str | None = None
    category_secondary: list[str] = Field(default_factory=list)
    category_confidence: float | None = None

    sentiment_label: str | None = None
    sentiment_score: float | None = None

    summary_short: str | None = None
    summary_long: str | None = None


class ArticleEnrichmentOut(BaseModel):
    category_primary: str | None = None
    category_secondary: list[str] = Field(default_factory=list)
    category_confidence: float | None = None
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    summary_short: str | None = None
    summary_long: str | None = None
    model_versions: dict[str, str] = Field(default_factory=dict)

