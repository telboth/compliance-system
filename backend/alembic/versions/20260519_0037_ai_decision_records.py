"""Legg til ai_decision_records-tabellen (AI Governance).

Revision ID: 20260519_0037
Revises: 20260519_0036
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260519_0037"
down_revision = "20260519_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_decision_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", sa.String(length=128), nullable=False),
        sa.Column("model_provider", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("overall_confidence", sa.Float(), nullable=True),
        sa.Column("low_confidence_fields", sa.Text(), nullable=True),
        sa.Column("eu_ai_act_category", sa.String(length=32), nullable=False, server_default="limited_risk"),
        sa.Column("annex_iii_class", sa.String(length=64), nullable=True),
        sa.Column("requires_human_oversight", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("decision_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("raw_extraction_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_id", name="uq_ai_decision_records_invoice_id"),
    )
    op.create_index("ix_ai_decision_records_invoice_id", "ai_decision_records", ["invoice_id"], unique=True)
    op.create_index("ix_ai_decision_records_model_id", "ai_decision_records", ["model_id"])
    op.create_index("ix_ai_decision_records_eu_ai_act_category", "ai_decision_records", ["eu_ai_act_category"])


def downgrade() -> None:
    op.drop_index("ix_ai_decision_records_eu_ai_act_category", table_name="ai_decision_records")
    op.drop_index("ix_ai_decision_records_model_id", table_name="ai_decision_records")
    op.drop_index("ix_ai_decision_records_invoice_id", table_name="ai_decision_records")
    op.drop_table("ai_decision_records")
