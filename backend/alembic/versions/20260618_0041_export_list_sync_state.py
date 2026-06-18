"""Ny tabell export_list_sync_state for automatisk vareliste-oppdatering.

Revision ID: 20260618_0041
Revises: 20260618_0040
Create Date: 2026-06-18
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260618_0041"
down_revision = "20260618_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "export_list_sync_state",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("list_code", sa.String(length=4), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("last_etag", sa.String(length=256), nullable=True),
        sa.Column("last_modified", sa.String(length=64), nullable=True),
        sa.Column("current_version", sa.String(length=64), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_imported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="idle"),
        sa.Column("status_message", sa.String(length=512), nullable=True),
        sa.Column("last_imported_by", sa.String(length=128), nullable=True),
        sa.Column("item_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("list_code", name="uq_export_list_sync_state_list_code"),
    )
    op.create_index("ix_export_list_sync_state_list_code", "export_list_sync_state", ["list_code"])


def downgrade() -> None:
    op.drop_index("ix_export_list_sync_state_list_code", table_name="export_list_sync_state")
    op.drop_table("export_list_sync_state")
