"""Celery-task for LLM-ekstraksjon av invoice."""

from __future__ import annotations

from uuid import UUID

from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.extract_invoice.run")
def run(invoice_id: str) -> None:
    """Kjør ekstraksjon i worker-prosess."""
    from app.core.database import get_session_factory
    from app.services.extraction_service import run_extraction

    async def _run() -> None:
        async with get_session_factory()() as session:
            await run_extraction(session, UUID(invoice_id), model_id=None)

    run_async(_run())
