"""Legg til eksplisitt invoice pipeline event-logg.

Revision ID: 20260517_0020
Revises: 20260517_0019
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260517_0020"
down_revision = "20260517_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_pipeline_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("status_from", sa.String(length=32), nullable=True),
        sa.Column("status_to", sa.String(length=32), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_pipeline_events")),
    )
    op.create_index(op.f("ix_invoice_pipeline_events_invoice_id"), "invoice_pipeline_events", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_invoice_pipeline_events_stage"), "invoice_pipeline_events", ["stage"], unique=False)
    op.create_index(op.f("ix_invoice_pipeline_events_action"), "invoice_pipeline_events", ["action"], unique=False)
    op.create_index(op.f("ix_invoice_pipeline_events_created_at"), "invoice_pipeline_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_invoice_pipeline_events_created_at"), table_name="invoice_pipeline_events")
    op.drop_index(op.f("ix_invoice_pipeline_events_action"), table_name="invoice_pipeline_events")
    op.drop_index(op.f("ix_invoice_pipeline_events_stage"), table_name="invoice_pipeline_events")
    op.drop_index(op.f("ix_invoice_pipeline_events_invoice_id"), table_name="invoice_pipeline_events")
    op.drop_table("invoice_pipeline_events")
