"""Legg til agreements og agreement_check_results tabeller.

Revision ID: 20260517_0023
Revises: 20260517_0022
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260517_0023"
down_revision = "20260517_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agreements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("reference", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.String(length=512), nullable=True),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("extracted_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("extraction_model", sa.String(length=128), nullable=True),
        sa.Column("extraction_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agreements")),
    )
    op.create_index(op.f("ix_agreements_name"), "agreements", ["name"], unique=False)
    op.create_index(op.f("ix_agreements_is_active"), "agreements", ["is_active"], unique=False)

    op.create_table(
        "agreement_check_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("agreement_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("compliant", sa.Boolean(), nullable=False),
        sa.Column("deviations", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("checked_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agreement_check_results")),
    )
    op.create_index(op.f("ix_agreement_check_results_agreement_id"), "agreement_check_results", ["agreement_id"], unique=False)
    op.create_index(op.f("ix_agreement_check_results_invoice_id"), "agreement_check_results", ["invoice_id"], unique=False)
    op.create_index(op.f("ix_agreement_check_results_checked_at"), "agreement_check_results", ["checked_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agreement_check_results_checked_at"), table_name="agreement_check_results")
    op.drop_index(op.f("ix_agreement_check_results_invoice_id"), table_name="agreement_check_results")
    op.drop_index(op.f("ix_agreement_check_results_agreement_id"), table_name="agreement_check_results")
    op.drop_table("agreement_check_results")
    op.drop_index(op.f("ix_agreements_is_active"), table_name="agreements")
    op.drop_index(op.f("ix_agreements_name"), table_name="agreements")
    op.drop_table("agreements")
