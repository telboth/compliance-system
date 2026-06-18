"""Legg til CAS-numre, synonymer og HS-koder på export_control_items.

Revision ID: 20260618_0040
Revises: 20260520_0039
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260618_0040"
down_revision = "20260520_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "export_control_items",
        sa.Column("cas_numbers", sa.Text, nullable=True),
    )
    op.add_column(
        "export_control_items",
        sa.Column("synonyms", sa.Text, nullable=True),
    )
    op.add_column(
        "export_control_items",
        sa.Column("hs_codes", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("export_control_items", "hs_codes")
    op.drop_column("export_control_items", "synonyms")
    op.drop_column("export_control_items", "cas_numbers")
