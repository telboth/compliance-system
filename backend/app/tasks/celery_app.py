"""Celery-applikasjon for asynkron bakgrunnsprosessering."""

from __future__ import annotations

import asyncio

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init

from app.core.config import get_settings

settings = get_settings()


@worker_process_init.connect
def _reset_db_pool_after_fork(**kwargs: object) -> None:
    """Kast arvede asyncpg-forbindelser etter fork.

    asyncpg-tilkoblingspoolen som ble opprettet i parent-prosessen er IKKE
    fork-safe. Forked Celery-workers arver filbeskrivere og intern tilstand
    fra poolen, men kjører i en annen event-loop. Uten dispose() vil commits
    tilsynelatende lykkes (ingen exception) men data skrives ikke til databasen
    fordi asyncpg-forbindelsen sender til feil socket/loop.

    Løsning: kall engine.dispose() umiddelbart etter fork. Dette tømmer poolen;
    neste gang en sesjon trenger en forbindelse, oppretter asyncpg en ny forbindelse
    i workerens egen event-loop (satt opp av async_runtime.run_async).

    I tillegg nullstilles async_runtime._loop slik at neste run_async() alltid
    lager en ny, ren event-loop i den forkede prosessen.
    """
    # Nullstill den persistente event-loopen i async_runtime
    from app.tasks import async_runtime as _ar
    if _ar._loop is not None and not _ar._loop.is_closed():
        try:
            _ar._loop.close()
        except Exception:
            pass
    _ar._loop = None

    # Kast arvede asyncpg-forbindelser
    from app.core.database import get_engine
    engine = get_engine()
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(engine.dispose())
    finally:
        loop.close()

celery_app = Celery(
    "xlent_compliance",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.process_invoice",
        "app.tasks.extract_invoice",
        "app.tasks.screen_entities",
        "app.tasks.extended_screen",
        "app.tasks.update_sanctions",
        "app.tasks.update_external_watchlists",
        "app.tasks.screening_watchdog",
    ],
)

watchdog_interval = max(1, min(60, int(settings.screening_watchdog_interval_minutes or 1)))
watchdog_schedule = (
    crontab(minute="*")
    if watchdog_interval == 1
    else crontab(minute=f"*/{watchdog_interval}")
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.celery_timezone,
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "daily-sanctions-refresh-0740": {
            "task": "app.tasks.update_sanctions.run_scheduled",
            "schedule": crontab(
                minute=settings.sanctions_refresh_minute,
                hour=settings.sanctions_refresh_hour,
            ),
        },
        "daily-external-watchlist-ingest": {
            "task": "app.tasks.update_external_watchlists.run_scheduled",
            "schedule": crontab(
                minute=settings.external_source_refresh_minute,
                hour=settings.external_source_refresh_hour,
            ),
        },
        "screening-watchdog-extracted-stale": {
            "task": "app.tasks.screening_watchdog.run_scheduled",
            "schedule": watchdog_schedule,
        },
    },
)
