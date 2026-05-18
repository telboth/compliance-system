"""Celery-taskpakke for bakgrunnsjobber."""

# Hold importene eksplisitte for sideeffekter (task-registrering i Celery).
from app.tasks import (  # noqa: F401
    extended_screen,
    extract_invoice,
    process_invoice,
    screen_entities,
    screening_watchdog,
    update_external_watchlists,
    update_sanctions,
)
