"""Celery-task for manuell sanksjonsoppdatering."""

from __future__ import annotations

from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.update_sanctions.run")
def run() -> dict[str, str]:
    """Oppdater lokale kilder + trigger yente-reindexering via /updatez."""
    from app.services.sanctions_refresh_service import run_sanctions_refresh_cycle_with_trigger

    async def _run() -> dict[str, str]:
        result = await run_sanctions_refresh_cycle_with_trigger(trigger="manual")
        return {
            "status": "ok" if result.started else "skipped",
            "message": result.message,
        }

    return run_async(_run())


@celery_app.task(name="app.tasks.update_sanctions.run_scheduled")
def run_scheduled() -> dict[str, str]:
    """Kjøres av Celery Beat for daglig oppdatering."""
    from app.services.sanctions_refresh_service import run_sanctions_refresh_cycle_with_trigger

    async def _run() -> dict[str, str]:
        result = await run_sanctions_refresh_cycle_with_trigger(trigger="scheduled")
        return {
            "status": "ok" if result.started else "skipped",
            "message": result.message,
        }

    return run_async(_run())
