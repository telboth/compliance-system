"""Legg til tabell for lokal ingest av eksterne watchlist-kilder.

Revision ID: 20260516_0015
Revises: 20260516_0014
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260516_0015"
down_revision = "20260516_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "external_watchlist_entries",
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("name_normalized", sa.String(length=512), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=True),
        sa.Column("sanctions_type", sa.String(length=256), nullable=True),
        sa.Column("listed_from", sa.String(length=64), nullable=True),
        sa.Column("listed_to", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_external_watchlist_entries")),
    )
    op.create_index(
        op.f("ix_external_watchlist_entries_source"),
        "external_watchlist_entries",
        ["source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_watchlist_entries_external_id"),
        "external_watchlist_entries",
        ["external_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_watchlist_entries_name"),
        "external_watchlist_entries",
        ["name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_external_watchlist_entries_name_normalized"),
        "external_watchlist_entries",
        ["name_normalized"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_external_watchlist_entries_name_normalized"),
        table_name="external_watchlist_entries",
    )
    op.drop_index(
        op.f("ix_external_watchlist_entries_name"),
        table_name="external_watchlist_entries",
    )
    op.drop_index(
        op.f("ix_external_watchlist_entries_external_id"),
        table_name="external_watchlist_entries",
    )
    op.drop_index(
        op.f("ix_external_watchlist_entries_source"),
        table_name="external_watchlist_entries",
    )
    op.drop_table("external_watchlist_entries")
