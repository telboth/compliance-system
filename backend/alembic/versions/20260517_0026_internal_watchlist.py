"""Legg til intern sperreliste (internal_watchlist).

Revision ID: 20260517_0026
Revises: 20260517_0025
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260517_0026"
down_revision = "20260517_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "internal_watchlist",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entry_type", sa.String(32), nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False, server_default="red"),
        sa.Column("added_by", sa.String(256), nullable=False, server_default="system"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_internal_watchlist_entry_type", "internal_watchlist", ["entry_type"])
    op.create_index("ix_internal_watchlist_value", "internal_watchlist", ["value"])
    op.create_index("ix_internal_watchlist_is_active", "internal_watchlist", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_internal_watchlist_is_active", "internal_watchlist")
    op.drop_index("ix_internal_watchlist_value", "internal_watchlist")
    op.drop_index("ix_internal_watchlist_entry_type", "internal_watchlist")
    op.drop_table("internal_watchlist")
