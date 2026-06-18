"""Celery-task for automatisk maanedlig sjekk av embargo-/sanksjonslanden.

Beat-schedule: forste mandag i maaneden kl. 03:30
(30 min etter vareliste-sjekken for aa spre lasten).
"""

from __future__ import annotations

from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.update_embargo_list.check_scheduled")
def check_scheduled() -> dict[str, object]:
    """Maanedlig sjekk — kalles av Celery Beat."""
    from app.core.database import get_session_factory
    from app.services.embargo_sync_service import check_for_updates

    async def _run() -> dict[str, object]:
        async with get_session_factory()() as session:
            result = await check_for_updates(session)
        return {"status": "ok", "result": result}

    return run_async(_run())


@celery_app.task(name="app.tasks.update_embargo_list.check_manual")
def check_manual() -> dict[str, object]:
    """Manuell sjekk trigget fra API."""
    from app.core.database import get_session_factory
    from app.services.embargo_sync_service import check_for_updates

    async def _run() -> dict[str, object]:
        async with get_session_factory()() as session:
            result = await check_for_updates(session)
        return {"status": "ok", "result": result}

    return run_async(_run())
