"""Lokal metadata for nedlastede sanksjonslister."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import UUIDPrimaryKeyMixin


class SanctionsList(UUIDPrimaryKeyMixin, Base):
    """Sporer status for lokal nedlasting/parsing per listekilde."""

    __tablename__ = "sanctions_lists"

    source: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    last_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    entry_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    update_status: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
