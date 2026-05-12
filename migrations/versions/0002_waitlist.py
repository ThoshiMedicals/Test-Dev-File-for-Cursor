"""Waitlist / Coming Soon tables.

Revision ID: 0002_waitlist
Revises: 0001_init
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0002_waitlist"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "waitlist_subscribers",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email_ciphertext", sa.Text(), nullable=False),
        sa.Column("email_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("interests", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("optional_feedback", sa.Text(), nullable=True),
        sa.Column("sentiment_label", sa.String(length=16), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("ai_personalized_summary", sa.Text(), nullable=True),
        sa.Column("ai_model_version", sa.String(length=128), nullable=True),
        sa.Column("consent_marketing", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email_fingerprint", name="uq_waitlist_email_fingerprint"),
    )
    op.create_index("ix_waitlist_subscribers_email_fingerprint", "waitlist_subscribers", ["email_fingerprint"], unique=False)
    op.create_index("ix_waitlist_subscribers_session_id", "waitlist_subscribers", ["session_id"], unique=False)
    op.create_index("ix_waitlist_subscribers_created_at", "waitlist_subscribers", ["created_at"], unique=False)

    op.create_table(
        "waitlist_interactions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("sentiment_label", sa.String(length=16), nullable=True),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_waitlist_interactions_session_id", "waitlist_interactions", ["session_id"], unique=False)
    op.create_index("ix_waitlist_interactions_event_type", "waitlist_interactions", ["event_type"], unique=False)
    op.create_index("ix_waitlist_interactions_sentiment_label", "waitlist_interactions", ["sentiment_label"], unique=False)
    op.create_index("ix_waitlist_interactions_created_at", "waitlist_interactions", ["created_at"], unique=False)
    op.create_index(
        "ix_waitlist_interactions_session_time",
        "waitlist_interactions",
        ["session_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("waitlist_interactions")
    op.drop_table("waitlist_subscribers")
