"""Audit Plan Management — planlagte compliance-revisjoner.

Hvert audit-plan-element representerer en tilbakevendende kontrollaktivitet
(f.eks. «Kvartalsvis sanksjonslisterevisjon», «Halvårlig anti-hvitvasking-gjennomgang»).

mark_completed() rykker frem next_due_date med frequency_days og setter
last_completed_at til nå.  Eventuelle overdue-poster oppdages via
is_overdue-property.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AuditPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Én planlagt compliance-revisjonsaktivitet."""

    __tablename__ = "audit_plans"

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hvem er ansvarlig
    owner: Mapped[str] = mapped_column(String(128), nullable=False)

    # Kategori (samme vokabular som policies)
    # 'sanctions' | 'export_control' | 'aml' | 'data_privacy' | 'other'
    category: Mapped[str] = mapped_column(String(64), nullable=False)

    # Frekvens i dager (f.eks. 90 = kvartalsvis, 180 = halvårlig, 365 = årlig)
    frequency_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # Neste planlagte gjennomføring
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Siste fullføring
    last_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_completed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Notat fra siste gjennomføring
    last_completion_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Aktiv / trukket tilbake
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_audit_plans_next_due_date", "next_due_date"),
        Index("ix_audit_plans_owner", "owner"),
        Index("ix_audit_plans_category", "category"),
        Index("ix_audit_plans_is_active", "is_active"),
    )
