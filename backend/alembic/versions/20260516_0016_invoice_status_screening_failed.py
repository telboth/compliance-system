"""Legg til invoice-statusen screening_failed.

Revision ID: 20260516_0016
Revises: 20260516_0015
Create Date: 2026-05-16
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260516_0016"
down_revision = "20260516_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS 'screening_failed'")


def downgrade() -> None:
    # Postgres støtter ikke enkel fjerning av enum-verdi uten full type-rebuild.
    # Vi lar derfor downgrade være no-op.
    pass

