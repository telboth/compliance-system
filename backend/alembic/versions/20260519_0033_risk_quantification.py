"""Legg til risikokvantifiserings-kolonner på invoices.

Revision ID: 20260519_0033
Revises: 20260519_0032
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260519_0033"
down_revision = "20260519_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("risk_exposure_nok", sa.Numeric(18, 2), nullable=True))
    op.add_column("invoices", sa.Column("currency_rate_nok", sa.Numeric(18, 6), nullable=True))
    op.add_column("invoices", sa.Column("risk_multiplier", sa.Numeric(6, 2), nullable=True))
    op.add_column("invoices", sa.Column("risk_quantified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_invoices_risk_quantified_at", "invoices", ["risk_quantified_at"])


def downgrade() -> None:
    op.drop_index("ix_invoices_risk_quantified_at", table_name="invoices")
    op.drop_column("invoices", "risk_quantified_at")
    op.drop_column("invoices", "risk_multiplier")
    op.drop_column("invoices", "currency_rate_nok")
    op.drop_column("invoices", "risk_exposure_nok")
