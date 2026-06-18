"""Ny tabell embargo_countries for DB-backed embargosjekk.

Revision ID: 20260618_0042
Revises: 20260618_0041
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260618_0042"
down_revision = "20260618_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "embargo_countries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("iso2", sa.String(length=2), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sources", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("source_version", sa.String(length=64), nullable=False, server_default="seed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("iso2", name="uq_embargo_countries_iso2"),
    )
    op.create_index("ix_embargo_countries_iso2", "embargo_countries", ["iso2"])
    op.create_index("ix_embargo_countries_is_active", "embargo_countries", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_embargo_countries_is_active", table_name="embargo_countries")
    op.drop_index("ix_embargo_countries_iso2", table_name="embargo_countries")
    op.drop_table("embargo_countries")
