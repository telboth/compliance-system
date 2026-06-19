"""Celery-tasker for oppdatering av eksterne watchlist-kilder."""

from __future__ import annotations

from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app


def _task_result(result: dict[str, object]) -> dict[str, str]:
    if not result.get("started"):
        return {
            "status": "skipped",
            "message": str(result.get("message") or ""),
        }
    source_rows = result.get("sources")
    if isinstance(source_rows, list) and any(isinstance(row, dict) and row.get("status") == "failed" for row in source_rows):
        return {
            "status": "failed",
            "message": str(result.get("message") or ""),
        }
    return {
        "status": "ok",
        "message": str(result.get("message") or ""),
    }


@celery_app.task(name="app.tasks.update_external_watchlists.run")
def run() -> dict[str, str]:
    """Manuell oppdatering av UK sanctions og World Bank."""
    from app.services.external_watchlist_service import run_external_watchlist_ingest_cycle

    async def _run() -> dict[str, str]:
        result = await run_external_watchlist_ingest_cycle()
        return _task_result(result)

    return run_async(_run())


@celery_app.task(name="app.tasks.update_external_watchlists.run_scheduled")
def run_scheduled() -> dict[str, str]:
    """Planlagt daglig oppdatering av UK sanctions."""
    from app.services.external_watchlist_service import SOURCE_UK_SANCTIONS, run_external_watchlist_ingest_cycle

    async def _run() -> dict[str, str]:
        result = await run_external_watchlist_ingest_cycle(sources=(SOURCE_UK_SANCTIONS,))
        return _task_result(result)

    return run_async(_run())


@celery_app.task(name="app.tasks.update_external_watchlists.run_world_bank_monthly")
def run_world_bank_monthly() -> dict[str, str]:
    """Planlagt månedlig oppdatering av World Bank Debarred Firms and Individuals."""
    from app.services.external_watchlist_service import SOURCE_WORLD_BANK_DEBARRED, run_external_watchlist_ingest_cycle

    async def _run() -> dict[str, str]:
        result = await run_external_watchlist_ingest_cycle(sources=(SOURCE_WORLD_BANK_DEBARRED,))
        return _task_result(result)

    return run_async(_run())
