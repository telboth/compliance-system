"""Legg til compliance_policies og compliance_policy_versions tabeller.

Revision ID: 20260519_0035
Revises: 20260519_0034
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260519_0035"
down_revision = "20260519_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compliance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("owner", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_policies_category", "compliance_policies", ["category"])
    op.create_index("ix_compliance_policies_is_active", "compliance_policies", ["is_active"])

    op.create_table(
        "compliance_policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("compliance_policies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("change_summary", sa.String(length=512), nullable=True),
        sa.Column("law_references", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("effective_from", sa.String(length=32), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_id", "version_number", name="uq_policy_versions_policy_version"),
    )
    op.create_index("ix_policy_versions_policy_id", "compliance_policy_versions", ["policy_id"])
    op.create_index("ix_policy_versions_is_current", "compliance_policy_versions", ["is_current"])


def downgrade() -> None:
    op.drop_index("ix_policy_versions_is_current", table_name="compliance_policy_versions")
    op.drop_index("ix_policy_versions_policy_id", table_name="compliance_policy_versions")
    op.drop_table("compliance_policy_versions")
    op.drop_index("ix_compliance_policies_is_active", table_name="compliance_policies")
    op.drop_index("ix_compliance_policies_category", table_name="compliance_policies")
    op.drop_table("compliance_policies")
