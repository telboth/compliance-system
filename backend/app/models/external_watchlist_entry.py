"""Lokal normalisert lagring av eksterne watchlist-oppføringer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import UUIDPrimaryKeyMixin


class ExternalWatchlistEntry(UUIDPrimaryKeyMixin, Base):
    """En normalisert rad fra ekstern sanksjons-/debarred-kilde."""

    __tablename__ = "external_watchlist_entries"

    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    name_normalized: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sanctions_type: Mapped[str | None] = mapped_column(String(256), nullable=True)
    listed_from: Mapped[str | None] = mapped_column(String(64), nullable=True)
    listed_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

