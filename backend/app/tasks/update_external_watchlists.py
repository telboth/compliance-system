"""Celery-task for daglig ingest av eksterne watchlist-kilder."""

from __future__ import annotations

from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.update_external_watchlists.run")
def run() -> dict[str, str]:
    """Manuell ingest av eksterne kilder."""
    from app.services.external_watchlist_service import run_external_watchlist_ingest_cycle

    async def _run() -> dict[str, str]:
        result = await run_external_watchlist_ingest_cycle()
        return {
            "status": "ok" if result.get("started") else "skipped",
            "message": str(result.get("message") or ""),
        }

    return run_async(_run())


@celery_app.task(name="app.tasks.update_external_watchlists.run_scheduled")
def run_scheduled() -> dict[str, str]:
    """Planlagt daglig ingest av eksterne kilder."""
    from app.services.external_watchlist_service import run_external_watchlist_ingest_cycle

    async def _run() -> dict[str, str]:
        result = await run_external_watchlist_ingest_cycle()
        return {
            "status": "ok" if result.get("started") else "skipped",
            "message": str(result.get("message") or ""),
        }

    return run_async(_run())
