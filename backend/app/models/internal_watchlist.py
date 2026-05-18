"""Intern sperreliste — entiteter som skal flagges automatisk ved screening."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WatchlistEntry(Base):
    __tablename__ = "internal_watchlist"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    entry_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    # entry_type kan være: "name" | "email_domain" | "country" | "regex"

    value: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="red")
    # severity: "yellow" | "red"

    added_by: Mapped[str] = mapped_column(String(256), nullable=False, default="system")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )
