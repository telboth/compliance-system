"""Legg til hard DB-beskyttelse mot duplikater i screening_results.

Revision ID: 20260515_0009
Revises: 20260515_0008
Create Date: 2026-05-15

Endringer:
  1) Rydder eksisterende duplikater i screening_results.
  2) Oppretter unik indeks som blokkerer nye duplikater.

Unikhetsnoekkel:
  (invoice_id, entity_id, dataset, coalesce(dataset_entity_id, ''),
   coalesce(matched_name, ''), status)
"""

from __future__ import annotations

from alembic import op

revision: str = "20260515_0009"
down_revision: str | None = "20260515_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fjern eksisterende duplikater, behold sterkeste/nyeste rad.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                ctid,
                row_number() OVER (
                    PARTITION BY
                        invoice_id,
                        entity_id,
                        dataset,
                        COALESCE(dataset_entity_id, ''),
                        COALESCE(matched_name, ''),
                        status
                    ORDER BY score DESC, screened_at DESC, id DESC
                ) AS rn
            FROM screening_results
        )
        DELETE FROM screening_results s
        USING ranked r
        WHERE s.ctid = r.ctid
          AND r.rn > 1
        """
    )

    # Hard beskyttelse: ingen nye duplikater kan lagres.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_screening_results_unique_hit
        ON screening_results (
            invoice_id,
            entity_id,
            dataset,
            COALESCE(dataset_entity_id, ''),
            COALESCE(matched_name, ''),
            status
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_screening_results_unique_hit")
