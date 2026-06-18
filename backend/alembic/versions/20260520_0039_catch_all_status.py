"""Legg til catch-all sluttbruker-status på invoices.

Revision ID: 20260520_0039
Revises: 20260520_0038
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260520_0039"
down_revision = "20260520_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("catch_all_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("catch_all_summary", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_invoices_catch_all_status", "invoices", ["catch_all_status"])


def downgrade() -> None:
    op.drop_index("ix_invoices_catch_all_status", table_name="invoices")
    op.drop_column("invoices", "catch_all_summary")
    op.drop_column("invoices", "catch_all_status")
