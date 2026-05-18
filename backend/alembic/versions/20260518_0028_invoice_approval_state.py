"""Materialiser approval_state på invoices med DB-synk.

Revision ID: 20260518_0028
Revises: 20260517_0027
Create Date: 2026-05-18
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260518_0028"
down_revision = "20260517_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    approval_state = postgresql.ENUM(
        "pending",
        "approved",
        "blocked",
        "not_required",
        "assessing",
        name="approval_state",
        create_type=True,
    )
    approval_state.create(bind, checkfirst=True)

    op.add_column(
        "invoices",
        sa.Column(
            "approval_state",
            postgresql.ENUM(name="approval_state", create_type=False),
            nullable=True,
        ),
    )

    # Backfill eksisterende rader fra status + compliance_score.
    op.execute(
        """
        UPDATE invoices
        SET approval_state = (
            CASE
                WHEN status = 'approved' THEN 'approved'
                WHEN status = 'blocked' THEN 'blocked'
                WHEN compliance_score IN ('yellow', 'red') THEN 'pending'
                WHEN compliance_score = 'green' THEN 'not_required'
                ELSE 'assessing'
            END
        )::approval_state
        """
    )

    op.alter_column(
        "invoices",
        "approval_state",
        existing_type=postgresql.ENUM(name="approval_state", create_type=False),
        nullable=False,
        server_default="assessing",
    )
    op.create_index("ix_invoices_approval_state", "invoices", ["approval_state"])

    # Hard DB-beskyttelse: hold approval_state synket ved INSERT/UPDATE.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION invoices_set_approval_state()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.approval_state := (
                CASE
                    WHEN NEW.status = 'approved' THEN 'approved'
                    WHEN NEW.status = 'blocked' THEN 'blocked'
                    WHEN NEW.compliance_score IN ('yellow', 'red') THEN 'pending'
                    WHEN NEW.compliance_score = 'green' THEN 'not_required'
                    ELSE 'assessing'
                END
            )::approval_state;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_invoices_set_approval_state
        BEFORE INSERT OR UPDATE OF status, compliance_score
        ON invoices
        FOR EACH ROW
        EXECUTE FUNCTION invoices_set_approval_state();
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.execute("DROP TRIGGER IF EXISTS trg_invoices_set_approval_state ON invoices")
    op.execute("DROP FUNCTION IF EXISTS invoices_set_approval_state")
    op.drop_index("ix_invoices_approval_state", table_name="invoices")
    op.drop_column("invoices", "approval_state")
    postgresql.ENUM(name="approval_state").drop(bind, checkfirst=True)

