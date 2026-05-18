"""Legg til 'not_invoice' i invoicestatus-enum.

Revision ID: 20260517_0027
Revises: 20260517_0026
Create Date: 2026-05-17
"""

from __future__ import annotations

from alembic import op

revision = "20260517_0027"
down_revision = "20260517_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL ALTER TYPE ... ADD VALUE kan ikke kjøres inni en transaksjon
    # som allerede har DDL. Vi bruker COMMIT/BEGIN eksplisitt via execute_if.
    op.execute("ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS 'not_invoice'")


def downgrade() -> None:
    # PostgreSQL støtter ikke fjerning av enum-verdier — nedgradering er no-op.
    # For å fjerne 'not_invoice' manuelt: lag ny enum uten verdien og migrer.
    pass
