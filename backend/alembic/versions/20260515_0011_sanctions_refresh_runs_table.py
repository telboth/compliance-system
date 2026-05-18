"""Legg til tabell for kjorehistorikk pa sanksjonsoppdateringer.

Revision ID: 20260515_0011
Revises: 20260515_0010
Create Date: 2026-05-15
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_0011"
down_revision: str | None = "20260515_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sanctions_refresh_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("message", sa.String(length=1024), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sanctions_refresh_runs")),
    )
    op.create_index(
        op.f("ix_sanctions_refresh_runs_status"),
        "sanctions_refresh_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sanctions_refresh_runs_trigger"),
        "sanctions_refresh_runs",
        ["trigger"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sanctions_refresh_runs_trigger"), table_name="sanctions_refresh_runs")
    op.drop_index(op.f("ix_sanctions_refresh_runs_status"), table_name="sanctions_refresh_runs")
    op.drop_table("sanctions_refresh_runs")
