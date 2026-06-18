"""ExportListSyncState — sporingstabell for automatisk vareliste-oppdatering.

En rad per liste (list_code "I" og "II"). Celery Beat sjekker månedlig om
kilden har ny versjon (HTTP ETag/Last-Modified). Admins og brukere varsles
via notification_service, og hvem som helst kan trigge selve importen.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ExportListSyncState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tilstand for én vareliste-kilde."""

    __tablename__ = "export_list_sync_state"

    # "I" (militært / Wassenaar ML) | "II" (dual-use / EU Annex I)
    list_code: Mapped[str] = mapped_column(String(4), nullable=False, unique=True, index=True)

    # Konfigurerbar nedlastings-URL (settes av admin eller via env-variabel)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # HTTP ETag fra forrige vellykket nedlasting — brukes til betinget GET
    last_etag: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # Last-Modified-header fra forrige nedlasting (ISO-streng)
    last_modified: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Versjonstreng vi setter selv: "EU-2021/821-2024-09", "deksa-seed" osv.
    current_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Tidspunkter
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # "idle" | "checking" | "update_available" | "importing" | "ok" | "error"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")

    # Menneskelig lesbar statusmelding / feilmelding
    status_message: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Hvem trigget siste import (brukernavn eller "scheduled")
    last_imported_by: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Antall rader etter siste import
    item_count: Mapped[int | None] = mapped_column(nullable=True)
