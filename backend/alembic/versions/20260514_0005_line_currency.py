"""Legg til currency-kolonne på invoice_lines.

Revision ID: 20260514_0005
Revises: 20260514_0004
Create Date: 2026-05-14

Valuta per linje er nødvendig for fakturaer der linjer har ulik valuta
(f.eks. intercompany-transaksjoner), og for å knytte beløp tydelig til
riktig valutakode — særlig viktig for compliance-screening av beløpsgrenser.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260514_0005"
down_revision: str | None = "20260514_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "invoice_lines",
        sa.Column("currency", sa.String(3), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invoice_lines", "currency")
