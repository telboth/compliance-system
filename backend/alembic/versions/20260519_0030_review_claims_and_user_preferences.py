"""Legg til review-claim felter og persisted user preferences.

Revision ID: 20260519_0030
Revises: 20260519_0029
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260519_0030"
down_revision = "20260519_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("review_claimed_by", sa.String(length=128), nullable=True))
    op.add_column("invoices", sa.Column("review_claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_invoices_review_claimed_by", "invoices", ["review_claimed_by"], unique=False)
    op.create_index("ix_invoices_review_claimed_at", "invoices", ["review_claimed_at"], unique=False)

    op.create_table(
        "user_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_name", sa.String(length=128), nullable=False),
        sa.Column("preference_key", sa.String(length=64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_name", "preference_key", name="uq_user_preferences_actor_key"),
    )
    op.create_index("ix_user_preferences_actor_name", "user_preferences", ["actor_name"], unique=False)
    op.create_index("ix_user_preferences_preference_key", "user_preferences", ["preference_key"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_preferences_preference_key", table_name="user_preferences")
    op.drop_index("ix_user_preferences_actor_name", table_name="user_preferences")
    op.drop_table("user_preferences")

    op.drop_index("ix_invoices_review_claimed_at", table_name="invoices")
    op.drop_index("ix_invoices_review_claimed_by", table_name="invoices")
    op.drop_column("invoices", "review_claimed_at")
    op.drop_column("invoices", "review_claimed_by")

