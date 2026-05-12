from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class WaitlistSubscribeIn(BaseModel):
    email: EmailStr
    interests: list[str] = Field(default_factory=list, max_length=20)
    session_id: str | None = Field(default=None, max_length=64)
    optional_feedback: str | None = Field(default=None, max_length=4000)
    consent_marketing: bool = True


class WaitlistSubscribeOut(BaseModel):
    id: uuid.UUID
    status: str
    interests: list[str]
    sentiment_label: str | None = None
    sentiment_score: float | None = None
    message: str | None = None


class WaitlistInteractionIn(BaseModel):
    session_id: str = Field(..., max_length=64)
    event_type: str = Field(..., max_length=64)
    meta: dict = Field(default_factory=dict)


class WaitlistInteractionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    sentiment_label: str | None = None
    sentiment_score: float | None = None


class WaitlistConfigOut(BaseModel):
    interests: list[str]
