"""
Strukturert logging via structlog.

Vi bruker structlog i hele backend-en — aldri `print` eller `logging`-modulen
direkte. Strukturerte logger gjør det mulig å søke i og aggregere logger i
produksjon, og holder oss unna å logge persondata i klartekst.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """Konfigurer structlog. Kalles én gang fra `app.main` ved oppstart."""
    settings = get_settings()

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Hent en logger. Bruk modulnavn som `name` for sporbarhet."""
    return structlog.get_logger(name)
