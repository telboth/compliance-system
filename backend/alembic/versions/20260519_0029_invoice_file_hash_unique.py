"""Legg til SHA-256 fingerprint på invoice-filer med hard duplikatvern.

Revision ID: 20260519_0029
Revises: 20260518_0028
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260519_0029"
down_revision = "20260518_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("file_sha256", sa.String(length=64), nullable=True))
    op.create_index("ix_invoices_file_sha256", "invoices", ["file_sha256"], unique=False)
    op.create_index(
        "uq_invoices_file_sha256_not_null",
        "invoices",
        ["file_sha256"],
        unique=True,
        postgresql_where=sa.text("file_sha256 IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_invoices_file_sha256_not_null", table_name="invoices")
    op.drop_index("ix_invoices_file_sha256", table_name="invoices")
    op.drop_column("invoices", "file_sha256")

