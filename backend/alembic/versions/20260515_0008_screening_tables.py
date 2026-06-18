"""Legg til screening_results-tabell for sanksjonsscreening.

Revision ID: 20260515_0008
Revises: 20260515_0007
Create Date: 2026-05-15

Endringer:
  screening_results  — ett rad per (entity, datasett)-kombinasjon fra yente.
  match_status enum  — clear | potential_match | confirmed_match

Implementasjon:
  Bruker raa SQL (op.execute) i stedet for sa.Enum i op.create_table.
  Bakgrunn: SQLAlchemy sin _on_table_create-event for Enum-kolonner prover
  aa opprette typen paa nytt selv med create_type=False, noe som gir
  DuplicateObjectError om typen allerede finnes fra et tidligere kjoer.
  Raa SQL med IF NOT EXISTS gjoer migrasjonen fullt idempotent.
"""

from __future__ import annotations

from alembic import op

revision: str = "20260515_0008"
down_revision: str | None = "20260515_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enum-type — DO-blokk gjoer den idempotent (IF NOT EXISTS finnes ikke for TYPE i PG)
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE match_status AS ENUM (
                'clear',
                'potential_match',
                'confirmed_match'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    # Tabell — IF NOT EXISTS gjoer den idempotent
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS screening_results (
            id                UUID            PRIMARY KEY,
            invoice_id        UUID            NOT NULL
                REFERENCES invoices(id) ON DELETE CASCADE,
            entity_id         UUID            NOT NULL
                REFERENCES entities(id) ON DELETE CASCADE,
            dataset           VARCHAR(128)    NOT NULL,
            dataset_entity_id VARCHAR(256),
            matched_name      VARCHAR(512),
            score             NUMERIC(5, 4)   NOT NULL,
            listed_on         DATE,
            status            match_status    NOT NULL,
            raw_response      JSONB,
            screened_at       TIMESTAMPTZ     NOT NULL DEFAULT now()
        )
        """
    )

    # Indekser
    op.execute("CREATE INDEX IF NOT EXISTS ix_screening_results_invoice_id ON screening_results (invoice_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_screening_results_entity_id ON screening_results (entity_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_screening_results_invoice_status ON screening_results (invoice_id, status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_screening_results_invoice_status")
    op.execute("DROP INDEX IF EXISTS ix_screening_results_entity_id")
    op.execute("DROP INDEX IF EXISTS ix_screening_results_invoice_id")
    op.execute("DROP TABLE IF EXISTS screening_results")
    op.execute("DROP TYPE IF EXISTS match_status")
