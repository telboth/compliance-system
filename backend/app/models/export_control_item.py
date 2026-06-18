"""ExportControlListItem — én rad per punkt i en eksportkontroll-vareliste.

Tabellen fylles av ``scripts/import_dual_use_list.py`` fra EU-kommisjonens
offisielle Annex I-Excel (Vareliste II / dual-use) og kan suppleres med
Vareliste I (militært materiell). Den gir eksakt tittel/beskrivelse for et
konkret kontrollnummer (f.eks. 6A001) når matchetjenesten finner en kode på
en fakturalinje.

Tabellen er rent referansedata — den endres bare ved import, ikke av
brukerhandlinger.
"""

from __future__ import annotations

from sqlalchemy import Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ExportControlListItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ett kontrollnummer i Vareliste I eller II."""

    __tablename__ = "export_control_items"

    # "I" (militært) | "II" (dual-use)
    list_code: Mapped[str] = mapped_column(String(4), nullable=False, index=True)

    # Kategori: "ML10" eller "6"
    category: Mapped[str] = mapped_column(String(8), nullable=False, index=True)

    # Gruppe A-E (kun dual-use), None for militært
    group: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Fullt kontrollnummer, normalisert uppercase: "6A001", "ML10", "5A002.a.1"
    item_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # Normalisert nøkkel for oppslag (uten punktum/mellomrom, uppercase)
    item_code_normalized: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Kontrollregime: Wassenaar | NSG | MTCR | AG | CWC
    regime: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Versjon/kilde for sporbarhet, f.eks. "EU-2021/821-2024-09" eller "deksa-seed"
    source_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    __table_args__ = (
        Index(
            "uq_export_control_item_code_source",
            "item_code_normalized",
            "source_version",
            unique=True,
        ),
        Index("ix_export_control_list_category", "list_code", "category"),
    )
