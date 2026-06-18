"""Regulatorisk Radar — én rad per unikt feed-oppslag."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RegulatoryAlert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Én regualtorisk varsling hentet fra ett eksternt RSS/Atom-feed."""

    __tablename__ = "regulatory_alerts"

    # Kilden (kortform, f.eks. "OFAC", "EUR-Lex", "HM Treasury", "UN SC")
    source: Mapped[str] = mapped_column(String(64), nullable=False)

    # URL til selve feeden (ikke enkeltoppslaget)
    feed_url: Mapped[str] = mapped_column(String(512), nullable=False)

    # Tittel, lenke og sammendrag fra feed-elementet
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Publiseringstidspunkt fra feeden (kan mangle)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Tidspunkt for når vi hentet elementet
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Unik nøkkel fra feeden (guid/id/link) — brukes for deduplisering
    guid: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)

    # Alvorlighetsgrad satt av parseren basert på kildenøkkelord
    # "info" | "warn" | "critical"
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")

    # Kategori fritekst (f.eks. "sanctions", "export_control", "aml")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Er det sendt en in-app-notifikasjon for dette varselet?
    is_notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_regulatory_alerts_source", "source"),
        Index("ix_regulatory_alerts_severity", "severity"),
        Index("ix_regulatory_alerts_published_at", "published_at"),
        Index("ix_regulatory_alerts_is_notified", "is_notified"),
        Index("ix_regulatory_alerts_guid", "guid", unique=True),
    )
