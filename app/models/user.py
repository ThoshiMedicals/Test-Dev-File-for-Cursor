from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    personalization_opt_in: Mapped[bool] = mapped_column(default=True, index=True)
    tone_preference: Mapped[str | None] = mapped_column(String(16), nullable=True)

    profile_embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    profile_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("external_id", name="uq_users_external_id"),
        Index("ix_users_personalization_opt_in", "personalization_opt_in"),
    )


class BanditState(Base):
    __tablename__ = "bandit_state"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_external_id: Mapped[str] = mapped_column(String(256), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    # Thompson sampling over a small set of weight presets; each arm tracks alpha/beta.
    arms: Mapped[list[dict]] = mapped_column(JSON, default=list)


class UserEvent(Base):
    __tablename__ = "user_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_external_id: Mapped[str] = mapped_column(String(256), index=True)
    article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    event_type: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    # Optional numeric signals (seconds, scroll percent, etc.)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    __table_args__ = (
        Index("ix_user_events_user_time", "user_external_id", "created_at"),
        Index("ix_user_events_article_time", "article_id", "created_at"),
    )

