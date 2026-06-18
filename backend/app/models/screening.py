"""ScreeningResult — resultat fra sanksjonsscreening av en enkelt entitet.

Ett rad per (entity_id, dataset)-kombinasjon som returneres fra yente.
For entiteter som er «clear» lagres ett rad med score=0.0 per screening-kjoring.

Tabellen bruker "siste run vinner"-strategi under MVP.
Ved ny screening slettes gamle rader for invoicen før nye resultater lagres.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.entity import Entity
    from app.models.invoice import Invoice


class MatchStatus(str, enum.Enum):
    """Utfall av en enkelt entitet-sjekk mot ett sanksjons-datasett.

    Terskler (konfigurerbart via Settings):
      confirmed_match  score >= 0.90  → red compliance_score
      potential_match  score >= 0.70  → yellow compliance_score
      clear            score <  0.70  → green  (bidrar ikke til eskalering)
    """

    CLEAR = "clear"
    POTENTIAL_MATCH = "potential_match"
    CONFIRMED_MATCH = "confirmed_match"


class ScreeningResult(UUIDPrimaryKeyMixin, Base):
    """Ett screening-treff fra yente for en spesifikk (entitet, datasett)-kombinasjon."""

    __tablename__ = "screening_results"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Yente-feltene
    dataset: Mapped[str] = mapped_column(String(128), nullable=False)
    dataset_entity_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    matched_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    listed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Beregnét utfall
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus, name="match_status", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )

    # Full yente-respons for sporbarhet og fremtidig analyse
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    screened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relasjoner
    invoice: Mapped[Invoice] = relationship("Invoice")
    entity: Mapped[Entity] = relationship("Entity")
