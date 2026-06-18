"""Legg til persisted kilder og claims for utvidet screening.

Revision ID: 20260516_0014
Revises: 20260516_0013
Create Date: 2026-05-16
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20260516_0014"
down_revision: str | None = "20260516_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extended_screen_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("source_title", sa.String(length=512), nullable=True),
        sa.Column("source_domain", sa.String(length=255), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["extended_screen_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extended_screen_sources")),
    )
    op.create_index(op.f("ix_extended_screen_sources_run_id"), "extended_screen_sources", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_extended_screen_sources_invoice_id"), "extended_screen_sources", ["invoice_id"], unique=False
    )
    op.create_index(
        op.f("ix_extended_screen_sources_entity_id"), "extended_screen_sources", ["entity_id"], unique=False
    )
    op.create_index(op.f("ix_extended_screen_sources_provider"), "extended_screen_sources", ["provider"], unique=False)

    op.create_table(
        "extended_screen_claims",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("claim_type", sa.String(length=64), nullable=False),
        sa.Column("claim_subject", sa.String(length=512), nullable=False),
        sa.Column("claim_object", sa.String(length=1024), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("verification_status", sa.String(length=16), nullable=False, server_default="unverified"),
        sa.Column("source_provider", sa.String(length=32), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=True),
        sa.Column("quoted_text", sa.String(length=2048), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["extended_screen_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_extended_screen_claims")),
    )
    op.create_index(op.f("ix_extended_screen_claims_run_id"), "extended_screen_claims", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_extended_screen_claims_invoice_id"), "extended_screen_claims", ["invoice_id"], unique=False
    )
    op.create_index(op.f("ix_extended_screen_claims_entity_id"), "extended_screen_claims", ["entity_id"], unique=False)
    op.create_index(
        op.f("ix_extended_screen_claims_claim_type"), "extended_screen_claims", ["claim_type"], unique=False
    )
    op.create_index(
        op.f("ix_extended_screen_claims_source_provider"), "extended_screen_claims", ["source_provider"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_extended_screen_claims_source_provider"), table_name="extended_screen_claims")
    op.drop_index(op.f("ix_extended_screen_claims_claim_type"), table_name="extended_screen_claims")
    op.drop_index(op.f("ix_extended_screen_claims_entity_id"), table_name="extended_screen_claims")
    op.drop_index(op.f("ix_extended_screen_claims_invoice_id"), table_name="extended_screen_claims")
    op.drop_index(op.f("ix_extended_screen_claims_run_id"), table_name="extended_screen_claims")
    op.drop_table("extended_screen_claims")

    op.drop_index(op.f("ix_extended_screen_sources_provider"), table_name="extended_screen_sources")
    op.drop_index(op.f("ix_extended_screen_sources_entity_id"), table_name="extended_screen_sources")
    op.drop_index(op.f("ix_extended_screen_sources_invoice_id"), table_name="extended_screen_sources")
    op.drop_index(op.f("ix_extended_screen_sources_run_id"), table_name="extended_screen_sources")
    op.drop_table("extended_screen_sources")
