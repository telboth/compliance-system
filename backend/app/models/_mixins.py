"""Gjenbrukbare modell-mixins."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """Standard UUID-primærnøkkel."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """`created_at` og `updated_at` håndtert av databasen.

    Merk: ``onupdate=func.now()`` er et ORM-nivå-signal — SQLAlchemy inkluderer
    ``updated_at = NOW()`` automatisk i UPDATE-setninger generert via ORM-session
    (``session.add`` / ``session.flush``).  Direkte bulk-oppdateringer via
    ``session.execute(update(...))`` trigger *ikke* ``onupdate`` automatisk;
    de må eksplisitt sette ``updated_at`` i ``.values()``.
    For robust server-side-oppdatering bør en PostgreSQL-trigger brukes
    dersom mange steder bruker bulk-UPDATE.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
