"""Legg til review-felter på Invoice.

Revision ID: 20260517_0024
Revises: 20260517_0023
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260517_0024"
down_revision = "20260517_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("review_decision", sa.String(16), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("review_reason", sa.Text, nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("reviewed_by", sa.String(128), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_invoices_review_decision", "invoices", ["review_decision"])
    op.create_index("ix_invoices_reviewed_at", "invoices", ["reviewed_at"])


def downgrade() -> None:
    op.drop_index("ix_invoices_reviewed_at", table_name="invoices")
    op.drop_index("ix_invoices_review_decision", table_name="invoices")
    op.drop_column("invoices", "reviewed_at")
    op.drop_column("invoices", "reviewed_by")
    op.drop_column("invoices", "review_reason")
    op.drop_column("invoices", "review_decision")
