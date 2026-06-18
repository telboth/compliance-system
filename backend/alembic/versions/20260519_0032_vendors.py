"""Legg til vendors-tabellen (Vendor Register).

Revision ID: 20260519_0032
Revises: 20260519_0031
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260519_0032"
down_revision = "20260519_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name_normalized", sa.String(length=512), nullable=False),
        sa.Column("name_display", sa.String(length=512), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("email_domain", sa.String(length=255), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="low"),
        sa.Column("invoice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("screening_hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("confirmed_hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name_normalized", "country", name="uq_vendors_name_country"),
    )
    op.create_index("ix_vendors_name_normalized", "vendors", ["name_normalized"])
    op.create_index("ix_vendors_risk_level", "vendors", ["risk_level"])
    op.create_index("ix_vendors_country", "vendors", ["country"])


def downgrade() -> None:
    op.drop_index("ix_vendors_country", table_name="vendors")
    op.drop_index("ix_vendors_risk_level", table_name="vendors")
    op.drop_index("ix_vendors_name_normalized", table_name="vendors")
    op.drop_table("vendors")
