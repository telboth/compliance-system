"""Legg til audit_plans-tabellen (Audit Plan Management).

Revision ID: 20260519_0036
Revises: 20260519_0035
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260519_0036"
down_revision = "20260519_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("frequency_days", sa.Integer(), nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_completed_by", sa.String(length=128), nullable=True),
        sa.Column("last_completion_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_plans_next_due_date", "audit_plans", ["next_due_date"])
    op.create_index("ix_audit_plans_owner", "audit_plans", ["owner"])
    op.create_index("ix_audit_plans_category", "audit_plans", ["category"])
    op.create_index("ix_audit_plans_is_active", "audit_plans", ["is_active"])


def downgrade() -> None:
    op.drop_index("ix_audit_plans_is_active", table_name="audit_plans")
    op.drop_index("ix_audit_plans_category", table_name="audit_plans")
    op.drop_index("ix_audit_plans_owner", table_name="audit_plans")
    op.drop_index("ix_audit_plans_next_due_date", table_name="audit_plans")
    op.drop_table("audit_plans")
