"""Legg til rule og rule_versions tabeller (regelmotor).

Revision ID: 20260517_0022
Revises: 20260517_0021
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260517_0022"
down_revision = "20260517_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Severity enum
    op.execute("CREATE TYPE rule_severity AS ENUM ('green', 'yellow', 'red')")

    op.create_table(
        "rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", postgresql.ENUM("green", "yellow", "red", name="rule_severity", create_type=False), nullable=False, server_default="yellow"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("active_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rules")),
        sa.UniqueConstraint("name", name=op.f("uq_rules_name")),
    )
    op.create_index(op.f("ix_rules_name"), "rules", ["name"], unique=True)
    op.create_index(op.f("ix_rules_is_active"), "rules", ["is_active"], unique=False)

    op.create_table(
        "rule_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rule_yaml", sa.Text(), nullable=False),
        sa.Column("rule_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("comment", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_versions")),
    )
    op.create_index(op.f("ix_rule_versions_rule_id"), "rule_versions", ["rule_id"], unique=False)
    op.create_index(op.f("ix_rule_versions_created_at"), "rule_versions", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rule_versions_created_at"), table_name="rule_versions")
    op.drop_index(op.f("ix_rule_versions_rule_id"), table_name="rule_versions")
    op.drop_table("rule_versions")
    op.drop_index(op.f("ix_rules_is_active"), table_name="rules")
    op.drop_index(op.f("ix_rules_name"), table_name="rules")
    op.drop_table("rules")
    op.execute("DROP TYPE rule_severity")
