"""Legg til geocode-cache for forsendelseskart.

Revision ID: 20260517_0019
Revises: 20260517_0018
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260517_0019"
down_revision = "20260517_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "geocode_cache",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("cache_key", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("query_text", sa.String(length=512), nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("precision_level", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("hit_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_geocode_cache")),
    )
    op.create_index(op.f("ix_geocode_cache_cache_key"), "geocode_cache", ["cache_key"], unique=True)
    op.create_index(op.f("ix_geocode_cache_provider"), "geocode_cache", ["provider"], unique=False)
    op.create_index(op.f("ix_geocode_cache_country_code"), "geocode_cache", ["country_code"], unique=False)
    op.create_index(op.f("ix_geocode_cache_precision_level"), "geocode_cache", ["precision_level"], unique=False)
    op.create_index(op.f("ix_geocode_cache_status"), "geocode_cache", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_geocode_cache_status"), table_name="geocode_cache")
    op.drop_index(op.f("ix_geocode_cache_precision_level"), table_name="geocode_cache")
    op.drop_index(op.f("ix_geocode_cache_country_code"), table_name="geocode_cache")
    op.drop_index(op.f("ix_geocode_cache_provider"), table_name="geocode_cache")
    op.drop_index(op.f("ix_geocode_cache_cache_key"), table_name="geocode_cache")
    op.drop_table("geocode_cache")
