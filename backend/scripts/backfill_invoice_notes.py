"""Backfill invoice note fields for existing invoices.

Run:
  docker compose exec api python -m scripts.backfill_invoice_notes
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.models.invoice import Invoice
from app.services.invoice_note_service import apply_invoice_notes

logger = get_logger(__name__)


async def main() -> None:
    updated = 0
    scanned = 0
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Invoice).options(selectinload(Invoice.entities)).order_by(Invoice.created_at.desc())
        )
        invoices = list(result.scalars().all())
        scanned = len(invoices)
        for invoice in invoices:
            before = (
                invoice.vat_note_status,
                invoice.vat_note_text,
                invoice.email_note_status,
                invoice.email_note_text,
                invoice.llm_note_preview,
            )
            apply_invoice_notes(invoice)
            after = (
                invoice.vat_note_status,
                invoice.vat_note_text,
                invoice.email_note_status,
                invoice.email_note_text,
                invoice.llm_note_preview,
            )
            if before != after:
                updated += 1
        await session.commit()

    logger.info("invoice_notes_backfilled", scanned=scanned, updated=updated)
    print(f"Scanned={scanned}, updated={updated}")


if __name__ == "__main__":
    asyncio.run(main())
