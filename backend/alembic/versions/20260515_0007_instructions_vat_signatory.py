"""Legg til instructions, vat-felt og signatory-rolle.

Revision ID: 20260515_0007
Revises: 20260514_0006
Create Date: 2026-05-15

Endringer:
  invoices:   + instructions TEXT          — verbatim instruksjoner/notater fra dokumentet
              + vat_amount  NUMERIC(18,2)  — MVA-beløp i fakturavaluta
              + vat_rate    VARCHAR(20)    — MVA-sats (f.eks. "25%", "VAT exempt")
  entity_role enum: + signatory           — person som har signert/autorisert dokumentet
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_0007"
down_revision: str | None = "20260514_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nye kolonner på invoices
    op.add_column("invoices", sa.Column("instructions", sa.Text(), nullable=True))
    op.add_column("invoices", sa.Column("vat_amount", sa.Numeric(18, 2), nullable=True))
    op.add_column("invoices", sa.Column("vat_rate", sa.String(20), nullable=True))

    # Legg til ny verdi i entity_role-enum.
    # PostgreSQL støtter ikke fjerning av enum-verdier, så downgrade lar den stå.
    op.execute("ALTER TYPE entity_role ADD VALUE IF NOT EXISTS 'signatory'")


def downgrade() -> None:
    # Enum-verdier kan ikke fjernes i PostgreSQL — 'signatory' blir igjen.
    op.drop_column("invoices", "vat_rate")
    op.drop_column("invoices", "vat_amount")
    op.drop_column("invoices", "instructions")
