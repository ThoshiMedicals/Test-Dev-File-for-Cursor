from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserUpsertIn(BaseModel):
    external_id: str
    preferences: dict = Field(default_factory=dict)
    personalization_opt_in: bool = True
    tone_preference: str | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    external_id: str
    created_at: datetime
    preferences: dict
    personalization_opt_in: bool
    tone_preference: str | None


class UserEventIn(BaseModel):
    user_external_id: str
    article_id: uuid.UUID
    event_type: str
    value: float | None = None
    meta: dict = Field(default_factory=dict)


class RecommendationsOut(BaseModel):
    user_external_id: str
    items: list[dict] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)


class NotificationOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str | None
    topic_slug: str | None
    severity: str
    article_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime


class NotificationCreateIn(BaseModel):
    title: str = Field(..., max_length=512)
    body: str | None = Field(default=None, max_length=8000)
    topic_slug: str | None = Field(default=None, max_length=64)
    severity: str = Field(default="info", max_length=32)
    article_id: uuid.UUID | None = None

