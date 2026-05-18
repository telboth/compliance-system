"""Kjorelogg for manuelle og planlagte sanksjonsoppdateringer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import UUIDPrimaryKeyMixin


class SanctionsRefreshRun(UUIDPrimaryKeyMixin, Base):
    """Én rad per forsok pa refresh-syklus."""

    __tablename__ = "sanctions_refresh_runs"

    trigger: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
