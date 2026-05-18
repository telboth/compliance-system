"""Celery-task for sanksjonsscreening."""

from __future__ import annotations

from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select

from app.core.config import get_settings
from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app

_settings = get_settings()
_SCREENING_SOFT_TIMEOUT = max(
    30,
    int(getattr(_settings, "screening_task_soft_timeout_seconds", 120) or 120),
)
_SCREENING_HARD_TIMEOUT = max(
    _SCREENING_SOFT_TIMEOUT + 5,
    int(getattr(_settings, "screening_task_hard_timeout_seconds", 150) or 150),
)


@celery_app.task(
    name="app.tasks.screen_entities.run",
    soft_time_limit=_SCREENING_SOFT_TIMEOUT,
    time_limit=_SCREENING_HARD_TIMEOUT,
    bind=True,
    max_retries=8,
    default_retry_delay=10,
    acks_late=True,
    reject_on_worker_lost=True,
)
def run(self, invoice_id: str) -> None:
    """Kjør screening i worker-prosess."""
    from app.core.database import get_session_factory
    from app.models.invoice import InvoiceStatus
    from app.services.screening_service import (
        ScreeningLockUnavailableError,
        screen_invoice,
    )

    async def _mark_failed(error_message: str) -> None:
        async with get_session_factory()() as session:
            from datetime import UTC, datetime

            from app.models.screening_run import ScreeningRun
            from app.services.invoice_service import get_invoice

            invoice = await get_invoice(session, UUID(invoice_id))
            invoice.status = InvoiceStatus.SCREENING_FAILED
            invoice.compliance_score = None

            run_result = await session.execute(
                select(ScreeningRun)
                .where(ScreeningRun.invoice_id == invoice.id)
                .order_by(ScreeningRun.started_at.desc())
                .limit(1)
            )
            screening_run = run_result.scalars().first()
            if screening_run is not None and screening_run.status == "running":
                screening_run.status = "failed"
                screening_run.error_message = error_message[:2000]
                screening_run.finished_at = datetime.now(UTC)

            await session.commit()

    async def _run() -> None:
        async with get_session_factory()() as session:
            await screen_invoice(session, UUID(invoice_id))

    try:
        run_async(_run())
    except ScreeningLockUnavailableError as exc:
        # Midlertidig lock-konflikt betyr at en annen worker kjører samme invoice.
        # Retry i stedet for å markere "suksess" uten faktisk screening.
        raise self.retry(exc=exc) from exc
    except SoftTimeLimitExceeded:
        run_async(_mark_failed("Screening timed out i bakgrunnsjobb."))
        raise
    except Exception as exc:
        run_async(_mark_failed(f"Screening feilet: {exc}"))
        raise
