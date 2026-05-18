"""Cache av geokodede oppslag for kartvisning av forsendelser."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class GeocodeCache(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persist cache av geokoding for a unnga repeterte eksterne kall."""

    __tablename__ = "geocode_cache"

    cache_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, index=True)
    provider: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        default="nominatim",
    )
    query_text: Mapped[str] = mapped_column(String(512), nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    precision_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="success")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
