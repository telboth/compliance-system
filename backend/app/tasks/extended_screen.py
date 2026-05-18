"""Celery-task for utvidet screening."""

from __future__ import annotations

from uuid import UUID

from app.tasks.async_runtime import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.extended_screen.run")
def run(run_id: str) -> None:
    """Kjør utvidet screening i worker-prosess."""
    from app.services.extended_screening_service import execute_extended_screen_run

    run_async(execute_extended_screen_run(UUID(run_id)))
