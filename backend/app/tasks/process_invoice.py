"""Celery-task for parsing av invoice-dokumenter."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from app.tasks.celery_app import celery_app
from app.tasks.async_runtime import run_async


@celery_app.task(name="app.tasks.process_invoice.run")
def run(invoice_id: str, storage_path: str) -> None:
    """Kjør invoice-parsing i worker-prosess."""
    from app.services.invoice_service import parse_invoice_in_background

    run_async(parse_invoice_in_background(UUID(invoice_id), Path(storage_path)))
