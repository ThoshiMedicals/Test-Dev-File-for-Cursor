"""Initial schema.

Revision ID: 0001_init
Revises: 
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("homepage_url", sa.String(length=2048), nullable=True),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.create_index("ix_sources_name", "sources", ["name"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)
    op.create_index("ix_categories_name", "categories", ["name"], unique=True)

    op.create_table(
        "articles",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=True),
        sa.Column("raw_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("author", sa.String(length=256), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("lead_text", sa.Text(), nullable=True),
        sa.Column(
            "category_primary_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=True,
        ),
        sa.Column("category_secondary", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("category_confidence", sa.Float(), nullable=True),
        sa.Column("sentiment_label", sa.String(length=16), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("summary_short", sa.Text(), nullable=True),
        sa.Column("summary_long", sa.Text(), nullable=True),
        sa.Column("summary_model", sa.String(length=128), nullable=True),
        sa.Column("summary_prompt_version", sa.String(length=64), nullable=True),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("embedding_model", sa.String(length=128), nullable=True),
        sa.Column("llm_cache_key", sa.String(length=128), nullable=True),
        sa.UniqueConstraint("url", name="uq_articles_url"),
    )
    op.create_index("ix_articles_url", "articles", ["url"], unique=True)
    op.create_index("ix_articles_raw_hash", "articles", ["raw_hash"], unique=False)
    op.create_index("ix_articles_published_at", "articles", ["published_at"], unique=False)
    op.create_index("ix_articles_ingested_at", "articles", ["ingested_at"], unique=False)
    op.create_index("ix_articles_language", "articles", ["language"], unique=False)
    op.create_index("ix_articles_category_primary_id", "articles", ["category_primary_id"], unique=False)
    op.create_index("ix_articles_sentiment_label", "articles", ["sentiment_label"], unique=False)
    op.create_index("ix_articles_llm_cache_key", "articles", ["llm_cache_key"], unique=False)

    op.create_table(
        "users",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("personalization_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("tone_preference", sa.String(length=16), nullable=True),
        sa.Column("profile_embedding", sa.JSON(), nullable=True),
        sa.Column("profile_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("external_id", name="uq_users_external_id"),
    )
    op.create_index("ix_users_external_id", "users", ["external_id"], unique=True)
    op.create_index("ix_users_personalization_opt_in", "users", ["personalization_opt_in"], unique=False)

    op.create_table(
        "bandit_state",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_external_id", sa.String(length=256), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arms", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
    )
    op.create_index("ix_bandit_state_user_external_id", "bandit_state", ["user_external_id"], unique=False)

    op.create_table(
        "user_events",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_external_id", sa.String(length=256), nullable=False),
        sa.Column("article_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.create_index("ix_user_events_user_external_id", "user_events", ["user_external_id"], unique=False)
    op.create_index("ix_user_events_article_id", "user_events", ["article_id"], unique=False)
    op.create_index("ix_user_events_event_type", "user_events", ["event_type"], unique=False)
    op.create_index("ix_user_events_created_at", "user_events", ["created_at"], unique=False)
    op.create_index("ix_user_events_user_time", "user_events", ["user_external_id", "created_at"], unique=False)
    op.create_index("ix_user_events_article_time", "user_events", ["article_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("user_events")
    op.drop_table("bandit_state")
    op.drop_table("users")
    op.drop_table("articles")
    op.drop_table("categories")
    op.drop_table("sources")

