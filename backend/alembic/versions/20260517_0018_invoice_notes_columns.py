"""Legg til invoice-merknader for moms, epost og LLM-preview.

Revision ID: 20260517_0018
Revises: 20260516_0017
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260517_0018"
down_revision = "20260516_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("vat_note_status", sa.String(length=16), nullable=True))
    op.add_column("invoices", sa.Column("vat_note_text", sa.String(length=512), nullable=True))
    op.add_column("invoices", sa.Column("email_note_status", sa.String(length=16), nullable=True))
    op.add_column("invoices", sa.Column("email_note_text", sa.String(length=512), nullable=True))
    op.add_column("invoices", sa.Column("llm_note_preview", sa.String(length=512), nullable=True))

    op.create_index("ix_invoices_vat_note_status", "invoices", ["vat_note_status"], unique=False)
    op.create_index("ix_invoices_email_note_status", "invoices", ["email_note_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_invoices_email_note_status", table_name="invoices")
    op.drop_index("ix_invoices_vat_note_status", table_name="invoices")

    op.drop_column("invoices", "llm_note_preview")
    op.drop_column("invoices", "email_note_text")
    op.drop_column("invoices", "email_note_status")
    op.drop_column("invoices", "vat_note_text")
    op.drop_column("invoices", "vat_note_status")
