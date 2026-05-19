"""Vendor Register — én rad per unik leverandør/motpart."""

from __future__ import annotations

import uuid

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Vendor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """En unik motpart (leverandør, kjøper e.l.) identifisert på tvers av fakturaer.

    Registeret bygges opp automatisk under sanksjonsscreening:
    SELLER- og BUYER-entiteter lagres som vendors med nøkkel på normalisert navn
    + land. Risikoprofilen oppdateres etter hvert screening-runde.
    """

    __tablename__ = "vendors"

    # Normalisert navn (lowercase, stripped)
    name_normalized: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    # Originalt navn (sist sett)
    name_display: Mapped[str] = mapped_column(String(512), nullable=False)

    # Landkode (ISO 3166-1 alpha-2), kan mangle
    country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)

    # E-postdomene (sist sett, for intern referanse)
    email_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Risikoprofil — aggregert fra alle screeninger
    # "low" | "medium" | "high" | "critical"
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="low", index=True)

    # Antall fakturaer der denne leverandøren er involvert
    invoice_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Antall screeninger med treff (potential + confirmed)
    screening_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Antall screeninger med confirmed match
    confirmed_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Fritekst-notat fra compliance-ansvarlig
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Ekstern identifikator (f.eks. organisasjonsnummer, DUNS-nummer)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    __table_args__ = (
        Index("ix_vendors_name_normalized", "name_normalized"),
        Index("ix_vendors_risk_level", "risk_level"),
        Index("uq_vendors_name_country", "name_normalized", "country", unique=True),
    )
