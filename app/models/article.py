from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    homepage_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    raw_hash: Mapped[str] = mapped_column(String(64), index=True)

    title: Mapped[str] = mapped_column(String(1024))
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=True)
    source: Mapped[Source | None] = relationship()

    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    category_primary_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True, index=True
    )
    category_primary: Mapped[Category | None] = relationship(foreign_keys=[category_primary_id])
    category_secondary: Mapped[list[str]] = mapped_column(JSON, default=list)
    category_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    sentiment_label: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    summary_short: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_long: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary_prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    llm_cache_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("url", name="uq_articles_url"),
        Index("ix_articles_raw_hash", "raw_hash"),
    )

