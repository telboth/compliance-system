"""Legg til regulatory_alerts-tabellen (Regulatorisk Radar).

Revision ID: 20260519_0031
Revises: 20260519_0030
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260519_0031"
down_revision = "20260519_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "regulatory_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("feed_url", sa.String(length=512), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("link", sa.String(length=1024), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("guid", sa.String(length=1024), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("is_notified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guid", name="uq_regulatory_alerts_guid"),
    )
    op.create_index("ix_regulatory_alerts_guid", "regulatory_alerts", ["guid"], unique=True)
    op.create_index("ix_regulatory_alerts_source", "regulatory_alerts", ["source"])
    op.create_index("ix_regulatory_alerts_severity", "regulatory_alerts", ["severity"])
    op.create_index("ix_regulatory_alerts_published_at", "regulatory_alerts", ["published_at"])
    op.create_index("ix_regulatory_alerts_is_notified", "regulatory_alerts", ["is_notified"])


def downgrade() -> None:
    op.drop_index("ix_regulatory_alerts_is_notified", table_name="regulatory_alerts")
    op.drop_index("ix_regulatory_alerts_published_at", table_name="regulatory_alerts")
    op.drop_index("ix_regulatory_alerts_severity", table_name="regulatory_alerts")
    op.drop_index("ix_regulatory_alerts_source", table_name="regulatory_alerts")
    op.drop_index("ix_regulatory_alerts_guid", table_name="regulatory_alerts")
    op.drop_table("regulatory_alerts")
