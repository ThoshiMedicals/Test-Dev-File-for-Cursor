from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WaitlistSubscriber(Base):
    """Email stored encrypted at rest; fingerprint used for deduplication without decrypting."""

    __tablename__ = "waitlist_subscribers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    email_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    optional_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment_label: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    ai_personalized_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_model_version: Mapped[str | None] = mapped_column(String(128), nullable=True)

    consent_marketing: Mapped[bool] = mapped_column(default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("email_fingerprint", name="uq_waitlist_email_fingerprint"),)


class WaitlistInteraction(Base):
    """Anonymous session events for analytics, personalization training, and sentiment signals."""

    __tablename__ = "waitlist_interactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    sentiment_label: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    __table_args__ = (Index("ix_waitlist_interactions_session_time", "session_id", "created_at"),)
