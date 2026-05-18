"""Legg til tabell for MVP utvidet screening.

Revision ID: 20260515_0012
Revises: 20260515_0011
Create Date: 2026-05-15
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_0012"
down_revision: str | None = "20260515_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extended_screen_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("aggressiveness", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("summary_risk", sa.String(length=16), nullable=True),
        sa.Column("summary_text", sa.String(length=1024), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extended_screen_runs")),
    )
    op.create_index(
        op.f("ix_extended_screen_runs_invoice_id"),
        "extended_screen_runs",
        ["invoice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extended_screen_runs_entity_id"),
        "extended_screen_runs",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extended_screen_runs_status"),
        "extended_screen_runs",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_extended_screen_runs_status"), table_name="extended_screen_runs")
    op.drop_index(op.f("ix_extended_screen_runs_entity_id"), table_name="extended_screen_runs")
    op.drop_index(op.f("ix_extended_screen_runs_invoice_id"), table_name="extended_screen_runs")
    op.drop_table("extended_screen_runs")
