"""Legg til control_deviations-tabellen (Control Effectiveness).

Revision ID: 20260519_0034
Revises: 20260519_0033
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260519_0034"
down_revision = "20260519_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "control_deviations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("compliance_score_at_approval", sa.String(length=16), nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("deviation_type", sa.String(length=64), nullable=False),
        sa.Column("vendor_name", sa.String(length=512), nullable=True),
        sa.Column("destination_country", sa.String(length=2), nullable=True),
        sa.Column("is_repeat_vendor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reason_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_control_deviations_invoice_id", "control_deviations", ["invoice_id"])
    op.create_index("ix_control_deviations_deviation_type", "control_deviations", ["deviation_type"])
    op.create_index("ix_control_deviations_vendor_name", "control_deviations", ["vendor_name"])
    op.create_index("ix_control_deviations_is_repeat_vendor", "control_deviations", ["is_repeat_vendor"])


def downgrade() -> None:
    op.drop_index("ix_control_deviations_is_repeat_vendor", table_name="control_deviations")
    op.drop_index("ix_control_deviations_vendor_name", table_name="control_deviations")
    op.drop_index("ix_control_deviations_deviation_type", table_name="control_deviations")
    op.drop_index("ix_control_deviations_invoice_id", table_name="control_deviations")
    op.drop_table("control_deviations")
