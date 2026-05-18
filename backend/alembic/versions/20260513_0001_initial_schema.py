"""Initial schema — customers, invoices, invoice_lines, entities (Sprint 1).

Revision ID: 20260513_0001
Revises:
Create Date: 2026-05-13

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260513_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("org_number", sa.String(length=32), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=False, server_default="normal"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
    )
    op.create_index("ix_customers_name", "customers", ["name"])
    op.create_index("ix_customers_country", "customers", ["country"])
    op.create_index("ix_customers_org_number", "customers", ["org_number"])

    invoice_direction = postgresql.ENUM(
        "incoming", "outgoing", name="invoice_direction", create_type=True
    )
    invoice_direction.create(op.get_bind(), checkfirst=True)

    invoice_status = postgresql.ENUM(
        "uploaded",
        "parsing",
        "parsed",
        "parsing_failed",
        "extracting",
        "extracted",
        "screening",
        "screened",
        "reviewed",
        "approved",
        "blocked",
        name="invoice_status",
        create_type=True,
    )
    invoice_status.create(op.get_bind(), checkfirst=True)

    compliance_score = postgresql.ENUM(
        "green", "yellow", "red", name="compliance_score", create_type=True
    )
    compliance_score.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "invoices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_number", sa.String(length=64), nullable=True),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "direction",
            postgresql.ENUM(name="invoice_direction", create_type=False),
            nullable=False,
        ),
        sa.Column("pdf_path", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="invoice_status", create_type=False),
            nullable=False,
            server_default="uploaded",
        ),
        sa.Column("parsing_error", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column(
            "compliance_score",
            postgresql.ENUM(name="compliance_score", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invoices"),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="SET NULL",
            name="fk_invoices_customer_id_customers",
        ),
    )
    op.create_index("ix_invoices_invoice_number", "invoices", ["invoice_number"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_compliance_score", "invoices", ["compliance_score"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("product_code", sa.String(length=64), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("total_price", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_lines"),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            ondelete="CASCADE",
            name="fk_invoice_lines_invoice_id_invoices",
        ),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])
    op.create_index("ix_invoice_lines_product_code", "invoice_lines", ["product_code"])

    entity_type = postgresql.ENUM(
        "person", "company", "vessel", "aircraft", name="entity_type", create_type=True
    )
    entity_type.create(op.get_bind(), checkfirst=True)

    entity_role = postgresql.ENUM(
        "seller",
        "buyer",
        "end_user",
        "delivery_address",
        "other",
        name="entity_role",
        create_type=True,
    )
    entity_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column(
            "entity_type",
            postgresql.ENUM(name="entity_type", create_type=False),
            nullable=False,
        ),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM(name="entity_role", create_type=False),
            nullable=False,
        ),
        sa.Column("address", sa.String(length=1024), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_entities"),
        sa.ForeignKeyConstraint(
            ["invoice_id"],
            ["invoices.id"],
            ondelete="CASCADE",
            name="fk_entities_invoice_id_invoices",
        ),
    )
    op.create_index("ix_entities_invoice_id", "entities", ["invoice_id"])
    op.create_index("ix_entities_name", "entities", ["name"])
    op.create_index("ix_entities_country", "entities", ["country"])


def downgrade() -> None:
    op.drop_index("ix_entities_country", table_name="entities")
    op.drop_index("ix_entities_name", table_name="entities")
    op.drop_index("ix_entities_invoice_id", table_name="entities")
    op.drop_table("entities")

    op.drop_index("ix_invoice_lines_product_code", table_name="invoice_lines")
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")

    op.drop_index("ix_invoices_compliance_score", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_index("ix_invoices_invoice_number", table_name="invoices")
    op.drop_table("invoices")

    op.drop_index("ix_customers_org_number", table_name="customers")
    op.drop_index("ix_customers_country", table_name="customers")
    op.drop_index("ix_customers_name", table_name="customers")
    op.drop_table("customers")

    bind = op.get_bind()
    postgresql.ENUM(name="entity_role").drop(bind, checkfirst=True)
    postgresql.ENUM(name="entity_type").drop(bind, checkfirst=True)
    postgresql.ENUM(name="compliance_score").drop(bind, checkfirst=True)
    postgresql.ENUM(name="invoice_status").drop(bind, checkfirst=True)
    postgresql.ENUM(name="invoice_direction").drop(bind, checkfirst=True)
