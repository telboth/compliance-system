"""Add extraction columns to invoices (Sprint 2).

Revision ID: 20260513_0002
Revises: 20260513_0001
Create Date: 2026-05-13

Nye kolonner:
  extraction_confidence  JSONB   — konfidensscore per felt, inkl. low_confidence_fields
  extraction_error       TEXT    — feilmelding hvis ekstraksjon feilet
  extraction_model       VARCHAR — hvilken LLM-modell ble brukt
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260513_0002"
down_revision: str | None = "20260513_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Legg til extraction_failed-verdi i enum (kan ikke fjernes i downgrade)
    op.execute("ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS 'extraction_failed'")

    op.add_column(
        "invoices",
        sa.Column(
            "extraction_confidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Konfidensscore per felt fra LLM-ekstraksjon",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "extraction_error",
            sa.Text(),
            nullable=True,
            comment="Feilmelding hvis LLM-ekstraksjon feilet",
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "extraction_model",
            sa.String(length=128),
            nullable=True,
            comment="LLM-modell brukt til ekstraksjon",
        ),
    )


def downgrade() -> None:
    op.drop_column("invoices", "extraction_model")
    op.drop_column("invoices", "extraction_error")
    op.drop_column("invoices", "extraction_confidence")
