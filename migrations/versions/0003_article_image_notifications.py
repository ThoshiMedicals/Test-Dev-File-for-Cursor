"""Article image URL + user notifications.

Revision ID: 0003_article_image_notifications
Revises: 0002_waitlist
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0003_article_image_notifications"
down_revision = "0002_waitlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("image_url", sa.String(length=2048), nullable=True))

    op.create_table(
        "user_notifications",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_external_id", sa.String(length=256), nullable=False, index=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("topic_slug", sa.String(length=64), nullable=True, index=True),
        sa.Column("severity", sa.String(length=32), nullable=False, server_default="info"),
        sa.Column("article_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("articles.id"), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_notifications_user_created", "user_notifications", ["user_external_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("user_notifications")
    op.drop_column("articles", "image_url")
