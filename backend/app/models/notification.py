"""Notification — in-app varsel til brukere.

Varsler opprettes automatisk av pipeline-tjenestene og leses av
frontend via GET /api/v1/notifications?role=<rolle>.

Read-tracking skjer på klientsiden (localStorage) for å unngå
brukerspesifikke DB-rader i MVP-fasen uten real autentisering.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

if TYPE_CHECKING:
    pass


class Notification(Base):
    """Et in-app varsel."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False, default="info")
    """info | warn | error"""

    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """Lenker varselet til en spesifikk faktura (valgfritt)."""

    target_roles: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    """Liste over roller som skal se varselet, f.eks. ['compliance_officer', 'admin']."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
