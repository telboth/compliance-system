"""Legg til eksportkontroll-varelister (Vareliste I/II) og invoice-statuskolonner.

Revision ID: 20260520_0038
Revises: 20260519_0037
Create Date: 2026-05-20
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260520_0038"
down_revision = "20260519_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "export_control_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("list_code", sa.String(length=4), nullable=False),
        sa.Column("category", sa.String(length=8), nullable=False),
        sa.Column("group", sa.String(length=2), nullable=True),
        sa.Column("item_code", sa.String(length=32), nullable=False),
        sa.Column("item_code_normalized", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("regime", sa.String(length=16), nullable=True),
        sa.Column("source_version", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_code_normalized", "source_version", name="uq_export_control_item_code_source"),
    )
    op.create_index("ix_export_control_items_list_code", "export_control_items", ["list_code"])
    op.create_index("ix_export_control_items_category", "export_control_items", ["category"])
    op.create_index("ix_export_control_items_item_code", "export_control_items", ["item_code"])
    op.create_index(
        "ix_export_control_items_item_code_normalized",
        "export_control_items",
        ["item_code_normalized"],
    )
    op.create_index("ix_export_control_items_source_version", "export_control_items", ["source_version"])
    op.create_index(
        "ix_export_control_list_category",
        "export_control_items",
        ["list_code", "category"],
    )

    # Per-invoice eksportkontroll-status (analogt med vat_note_status)
    op.add_column(
        "invoices",
        sa.Column("export_control_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "invoices",
        sa.Column("export_control_summary", sa.String(length=512), nullable=True),
    )
    op.create_index(
        "ix_invoices_export_control_status",
        "invoices",
        ["export_control_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_export_control_status", table_name="invoices")
    op.drop_column("invoices", "export_control_summary")
    op.drop_column("invoices", "export_control_status")

    op.drop_index("ix_export_control_list_category", table_name="export_control_items")
    op.drop_index("ix_export_control_items_source_version", table_name="export_control_items")
    op.drop_index("ix_export_control_items_item_code_normalized", table_name="export_control_items")
    op.drop_index("ix_export_control_items_item_code", table_name="export_control_items")
    op.drop_index("ix_export_control_items_category", table_name="export_control_items")
    op.drop_index("ix_export_control_items_list_code", table_name="export_control_items")
    op.drop_table("export_control_items")
