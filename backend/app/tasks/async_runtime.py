"""Felles asyncio-runtime for Celery-worker-prosesser.

Celery kjører synkrone task-funksjoner. Når vi bruker async SQLAlchemy/httpx
må vi unngå `asyncio.run()` per task, siden det oppretter ny event loop hver
gang og kan gi "Future attached to a different loop" med gjenbrukte pools.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")

_loop: asyncio.AbstractEventLoop | None = None


def run_async[T](awaitable: Awaitable[T]) -> T:
    """Kjør awaitable i en stabil event loop per worker-prosess."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(awaitable)
