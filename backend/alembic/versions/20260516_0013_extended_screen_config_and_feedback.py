"""Legg til run_config og analyst-feedback for utvidet screening.

Revision ID: 20260516_0013
Revises: 20260515_0012
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260516_0013"
down_revision: str | None = "20260515_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "extended_screen_runs",
        sa.Column("run_config", sa.JSON(), nullable=True),
    )

    op.create_table(
        "extended_screen_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("feedback_label", sa.String(length=32), nullable=False),
        sa.Column("target_qid", sa.String(length=64), nullable=True),
        sa.Column("target_name", sa.String(length=512), nullable=True),
        sa.Column("note", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["extended_screen_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extended_screen_feedback")),
    )
    op.create_index(
        op.f("ix_extended_screen_feedback_run_id"),
        "extended_screen_feedback",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extended_screen_feedback_invoice_id"),
        "extended_screen_feedback",
        ["invoice_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_extended_screen_feedback_entity_id"),
        "extended_screen_feedback",
        ["entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_extended_screen_feedback_entity_id"), table_name="extended_screen_feedback")
    op.drop_index(op.f("ix_extended_screen_feedback_invoice_id"), table_name="extended_screen_feedback")
    op.drop_index(op.f("ix_extended_screen_feedback_run_id"), table_name="extended_screen_feedback")
    op.drop_table("extended_screen_feedback")
    op.drop_column("extended_screen_runs", "run_config")
