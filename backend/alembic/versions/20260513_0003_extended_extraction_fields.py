"""Extended extraction fields — forsendelse, linjer og entiteter.

Revision ID: 20260513_0003
Revises: 20260513_0002
Create Date: 2026-05-13

Nye kolonner:
  invoices:       incoterms, transport_mode, destination_country, po_number, comments
  invoice_lines:  hs_code, eccn, serial_number, model_number, country_of_origin, unit_of_measure
  entities:       phone, email
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260513_0003"
down_revision: str | None = "20260513_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # invoices
    op.add_column("invoices", sa.Column("incoterms", sa.String(10), nullable=True))
    op.add_column("invoices", sa.Column("transport_mode", sa.String(32), nullable=True))
    op.add_column("invoices", sa.Column("destination_country", sa.String(2), nullable=True))
    op.add_column("invoices", sa.Column("po_number", sa.String(128), nullable=True))
    op.add_column("invoices", sa.Column("comments", sa.Text(), nullable=True))
    op.create_index("ix_invoices_destination_country", "invoices", ["destination_country"])

    # invoice_lines
    op.add_column("invoice_lines", sa.Column("hs_code", sa.String(16), nullable=True))
    op.add_column("invoice_lines", sa.Column("eccn", sa.String(16), nullable=True))
    op.add_column("invoice_lines", sa.Column("serial_number", sa.String(256), nullable=True))
    op.add_column("invoice_lines", sa.Column("model_number", sa.String(256), nullable=True))
    op.add_column("invoice_lines", sa.Column("country_of_origin", sa.String(2), nullable=True))
    op.add_column("invoice_lines", sa.Column("unit_of_measure", sa.String(32), nullable=True))
    op.create_index("ix_invoice_lines_hs_code", "invoice_lines", ["hs_code"])
    op.create_index("ix_invoice_lines_eccn", "invoice_lines", ["eccn"])

    # entities
    op.add_column("entities", sa.Column("phone", sa.String(64), nullable=True))
    op.add_column("entities", sa.Column("email", sa.String(256), nullable=True))


def downgrade() -> None:
    op.drop_column("entities", "email")
    op.drop_column("entities", "phone")

    op.drop_index("ix_invoice_lines_eccn", table_name="invoice_lines")
    op.drop_index("ix_invoice_lines_hs_code", table_name="invoice_lines")
    op.drop_column("invoice_lines", "unit_of_measure")
    op.drop_column("invoice_lines", "country_of_origin")
    op.drop_column("invoice_lines", "model_number")
    op.drop_column("invoice_lines", "serial_number")
    op.drop_column("invoice_lines", "eccn")
    op.drop_column("invoice_lines", "hs_code")

    op.drop_index("ix_invoices_destination_country", table_name="invoices")
    op.drop_column("invoices", "comments")
    op.drop_column("invoices", "po_number")
    op.drop_column("invoices", "destination_country")
    op.drop_column("invoices", "transport_mode")
    op.drop_column("invoices", "incoterms")
