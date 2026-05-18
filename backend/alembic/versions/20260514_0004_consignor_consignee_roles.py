"""Legg til consignor og consignee som EntityRole-verdier.

Revision ID: 20260514_0004
Revises: 20260513_0003
Create Date: 2026-05-14

PostgreSQL støtter ikke fjerning av enum-verdier uten å rekreere typen,
så downgrade er en no-op. Nye verdier legges inn med IF NOT EXISTS for
idempotens.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260514_0004"
down_revision: str | None = "20260513_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL 12+ tillater ALTER TYPE ADD VALUE inne i en transaksjon,
    # så lenge de nye verdiene ikke brukes i samme transaksjon.
    # Vi legger dem inn med IF NOT EXISTS for idempotens.
    op.execute(sa.text("ALTER TYPE entity_role ADD VALUE IF NOT EXISTS 'consignor'"))
    op.execute(sa.text("ALTER TYPE entity_role ADD VALUE IF NOT EXISTS 'consignee'"))


def downgrade() -> None:
    # PostgreSQL støtter ikke DROP VALUE fra enum-typer.
    # For å rulle tilbake: DROP TYPE og recreate — gjøres manuelt ved behov.
    pass
