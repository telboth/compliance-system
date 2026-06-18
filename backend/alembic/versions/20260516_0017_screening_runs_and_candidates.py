"""Legg til screening_runs og screening_candidates for audit-snapshot.

Revision ID: 20260516_0017
Revises: 20260516_0016
Create Date: 2026-05-16
"""

from __future__ import annotations

from alembic import op

revision = "20260516_0017"
down_revision = "20260516_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS screening_runs (
            id              UUID            PRIMARY KEY,
            invoice_id      UUID            NOT NULL
                REFERENCES invoices(id) ON DELETE CASCADE,
            status          VARCHAR(16)     NOT NULL DEFAULT 'running',
            candidate_count INTEGER         NOT NULL DEFAULT 0,
            error_message   TEXT,
            started_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
            finished_at     TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_screening_runs_invoice_id ON screening_runs (invoice_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_screening_runs_status ON screening_runs (status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS screening_candidates (
            id              UUID            PRIMARY KEY,
            run_id          UUID            NOT NULL
                REFERENCES screening_runs(id) ON DELETE CASCADE,
            invoice_id      UUID            NOT NULL
                REFERENCES invoices(id) ON DELETE CASCADE,
            entity_id       UUID            NOT NULL
                REFERENCES entities(id) ON DELETE CASCADE,
            entity_name     VARCHAR(512),
            entity_role     VARCHAR(64),
            candidate_name  VARCHAR(512)    NOT NULL,
            entity_type     VARCHAR(64)     NOT NULL,
            country         VARCHAR(16),
            source          VARCHAR(64)     NOT NULL,
            source_email    VARCHAR(320),
            is_primary      BOOLEAN         NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ     NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_screening_candidates_run_id ON screening_candidates (run_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_screening_candidates_invoice_id ON screening_candidates (invoice_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_screening_candidates_entity_id ON screening_candidates (entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_screening_candidates_source ON screening_candidates (source)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_screening_candidates_source")
    op.execute("DROP INDEX IF EXISTS ix_screening_candidates_entity_id")
    op.execute("DROP INDEX IF EXISTS ix_screening_candidates_invoice_id")
    op.execute("DROP INDEX IF EXISTS ix_screening_candidates_run_id")
    op.execute("DROP TABLE IF EXISTS screening_candidates")
    op.execute("DROP INDEX IF EXISTS ix_screening_runs_status")
    op.execute("DROP INDEX IF EXISTS ix_screening_runs_invoice_id")
    op.execute("DROP TABLE IF EXISTS screening_runs")
