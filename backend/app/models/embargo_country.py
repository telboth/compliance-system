"""EmbargoCountry — databasetabell for landbaserte embargoer og sanksjoner.

Erstatter den hardkodede EMBARGO_LIST i app/sanctions/embargo.py.
Seedes fra den statiske listen ved oppstart dersom tabellen er tom.
Oppdateres via embargo_sync_service (maanedlig automatisk sjekk).
"""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class EmbargoCountry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ett sanksjonert land."""

    __tablename__ = "embargo_countries"

    # ISO 3166-1 alfa-2, uppercase. Unik indeks.
    iso2: Mapped[str] = mapped_column(String(2), nullable=False, unique=True, index=True)

    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Kommaseparert: "UN, EU, NO, US"
    sources: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    # "comprehensive" (totalforbud) | "sectoral" (sektorbasert)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Soft-delete: False = trukket tilbake / ikke lenger sanksjonert
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Versjonskilde: "seed", "auto-embargo-2026-06", osv.
    source_version: Mapped[str] = mapped_column(String(64), nullable=False, default="seed")
