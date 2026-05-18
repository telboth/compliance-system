"""AuditLog — append-only, hash-kjedet revisjonslogg.

Hvert innslag beregner sin SHA-256 hash over:
  previous_hash || invoice_id || action || actor || created_at_iso || details_json

Dette gjør det umulig å endre et historisk innslag uten å bryte kjeden.
Kravgrunnlag: EU AI Act Art. 12 (automatisk logging), GDPR Art. 5(2)
(ansvarlighet), SKILL.md §4 (audit log er hellig).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

if TYPE_CHECKING:
    pass


class AuditLog(Base):
    """Én enkelt hendelse i den hash-kjedede revisjonsloggen.

    Tabellen har ingen updated_at — rader skal aldri endres etter INSERT.
    DELETE-tillatelse bør fjernes fra applikasjonsbrukeren i produksjon.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Hva hendelsen gjelder (nullable: systemhendelser uten tilknyttet invoice)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Hva som skjedde — f.eks. "invoice.uploaded", "screening.completed",
    # "rule.triggered", "field.updated", "agreement.checked"
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    # Hvem utførte handlingen (brukernavn / system-komponent / "system")
    actor: Mapped[str] = mapped_column(
        String(128), nullable=False, default="system", index=True
    )

    # Strukturert kontekst — modellversjon, score, felt som ble endret, osv.
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Hash-kjede — SHA-256 (hex, 64 tegn)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    current_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
