"""Celery-task for automatisk maanedlig sjekk av DEKSAs varelister.

Beat-schedule: forste mandag i maaneden kl. 03:15.
Tasken sjekker kun om en ny versjon finnes (HTTP HEAD) og varsler alle brukere.
Selve importen trigges manuelt av en bruker via API-et.
"""

from __future__ import annotations

from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.update_export_lists.check_scheduled")
def check_scheduled() -> dict[str, object]:
    """Maanedlig sjekk — kalles av Celery Beat."""
    from app.core.database import get_session_factory
    from app.services.export_list_sync_service import check_for_updates

    async def _run() -> dict[str, object]:
        async with get_session_factory()() as session:
            results = await check_for_updates(session)
        return {"status": "ok", "results": results}

    return run_async(_run())


@celery_app.task(name="app.tasks.update_export_lists.check_manual")
def check_manual() -> dict[str, object]:
    """Manuell sjekk trigget fra API (bruker/admin)."""
    from app.core.database import get_session_factory
    from app.services.export_list_sync_service import check_for_updates

    async def _run() -> dict[str, object]:
        async with get_session_factory()() as session:
            results = await check_for_updates(session)
        return {"status": "ok", "results": results}

    return run_async(_run())
