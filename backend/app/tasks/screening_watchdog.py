"""Celery task: watchdog for EXTRACTED invoices som mangler screening."""

from __future__ import annotations

from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.screening_watchdog.run_scheduled")
def run_scheduled() -> dict[str, int | str]:
    """Kjøres av Celery Beat hvert N. minutt."""
    from app.services.screening_watchdog_service import (
        run_extracted_screening_watchdog_cycle,
    )

    return run_async(run_extracted_screening_watchdog_cycle())
