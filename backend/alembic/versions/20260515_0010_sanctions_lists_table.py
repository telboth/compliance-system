"""Legg til tabell for lokal sanksjonsliste-status.

Revision ID: 20260515_0010
Revises: 20260515_0009
Create Date: 2026-05-15
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_0010"
down_revision: str | None = "20260515_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sanctions_lists",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entry_count", sa.Integer(), nullable=True),
        sa.Column("update_status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sanctions_lists")),
    )
    op.create_index(
        op.f("ix_sanctions_lists_source"),
        "sanctions_lists",
        ["source"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sanctions_lists_source"), table_name="sanctions_lists")
    op.drop_table("sanctions_lists")
