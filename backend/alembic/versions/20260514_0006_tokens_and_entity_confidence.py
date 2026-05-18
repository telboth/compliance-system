"""Legg til token-kolonner på invoices og confidence på entities.

Revision ID: 20260514_0006
Revises: 20260514_0005
Create Date: 2026-05-14

Endringer:
  invoices:  + input_tokens INTEGER, + output_tokens INTEGER
             Lagrer faktisk token-forbruk per LLM-kjøring for kostnadssporing.
  entities:  + confidence DOUBLE PRECISION
             LLM-en gir konfidens per entitet — lagres nå slik at lav-
             konfidens-entiteter kan fremheves i UI og vektes i screening.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260514_0006"
down_revision: str | None = "20260514_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "invoices",
        sa.Column("input_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("output_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "entities",
        sa.Column("confidence", sa.Double(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("entities", "confidence")
    op.drop_column("invoices", "output_tokens")
    op.drop_column("invoices", "input_tokens")
