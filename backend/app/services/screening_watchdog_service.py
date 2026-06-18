"""Watchdog for invoices som blir hengende i EXTRACTED uten screening."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.models.invoice import Invoice, InvoiceStatus
from app.services.screening_service import ScreeningLockUnavailableError, screen_invoice

logger = get_logger(__name__)


async def run_extracted_screening_watchdog_cycle() -> dict[str, int | str]:
    """Finn stale EXTRACTED invoices og kjor screening."""
    settings = get_settings()

    if not settings.screening_watchdog_enabled:
        return {"status": "disabled", "checked": 0, "screened": 0, "failed": 0}
    if not settings.auto_screen_after_extract:
        return {"status": "skipped_auto_screen_off", "checked": 0, "screened": 0, "failed": 0}

    stale_minutes = max(1, int(settings.screening_watchdog_stale_minutes or 3))
    batch_size = max(1, min(200, int(settings.screening_watchdog_batch_size or 20)))
    stale_before = datetime.now(UTC) - timedelta(minutes=stale_minutes)

    async with get_session_factory()() as session:
        result = await session.execute(
            select(Invoice.id)
            .where(
                Invoice.status == InvoiceStatus.EXTRACTED,
                Invoice.updated_at <= stale_before,
            )
            .order_by(Invoice.updated_at.asc())
            .limit(batch_size)
        )
        invoice_ids = list(result.scalars().all())

    checked = len(invoice_ids)
    screened = 0
    skipped_lock = 0
    failed = 0

    for invoice_id in invoice_ids:
        try:
            async with get_session_factory()() as session:
                await screen_invoice(session, invoice_id)
            screened += 1
            logger.info("screening_watchdog_screened", invoice_id=str(invoice_id))
        except ScreeningLockUnavailableError:
            skipped_lock += 1
            logger.info("screening_watchdog_skip_lock", invoice_id=str(invoice_id))
        except Exception:
            failed += 1
            logger.exception("screening_watchdog_failed", invoice_id=str(invoice_id))

    logger.info(
        "screening_watchdog_cycle_completed",
        checked=checked,
        screened=screened,
        skipped_lock=skipped_lock,
        failed=failed,
        stale_minutes=stale_minutes,
        batch_size=batch_size,
    )

    return {
        "status": "ok",
        "checked": checked,
        "screened": screened,
        "skipped_lock": skipped_lock,
        "failed": failed,
    }
