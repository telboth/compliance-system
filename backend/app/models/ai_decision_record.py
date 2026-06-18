"""AI Governance — logg over AI-beslutninger iht. EU AI Act.

Én rad per invoice (UNIQUE på invoice_id).  Ved re-ekstraksjon brukes
INSERT ... ON CONFLICT DO UPDATE (upsert) for å bevare ett konsolidert
oppslag per faktura fremfor en voksende logg.

EU AI Act Annex III pkt. 8 (immigrasjon/grensekontroll er ikke relevant her),
men pkt. 2 (kritisk infrastruktur) og pkt. 6 (rettshåndheving) kan være
aktuelle avhengig av kunden.  Vi kategoriserer systemet konservativt som
«limited_risk» / «high_risk» basert på om det fatter binding compliance-
beslutninger autonomt.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AIDecisionRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Én AI-governance-post per invoice.

    Upsert-strategi: ved re-ekstraksjon oppdateres eksisterende rad;
    ingen duplikater per faktura.
    """

    __tablename__ = "ai_decision_records"

    # Én-til-én mot Invoice (UNIQUE)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        unique=True,
        index=True,
    )

    # Hvilken modell tok avgjørelsen
    model_id: Mapped[str] = mapped_column(String(128), nullable=False)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)

    # Token-forbruk
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Konfidens fra LLM (overall confidence, 0.0–1.0)
    overall_confidence: Mapped[float | None] = mapped_column(nullable=True)

    # Felter med lav konfidens (kommaseparert liste)
    low_confidence_fields: Mapped[str | None] = mapped_column(Text, nullable=True)

    # EU AI Act-kategorisering
    # "minimal_risk" | "limited_risk" | "high_risk"
    eu_ai_act_category: Mapped[str] = mapped_column(String(32), nullable=False, default="limited_risk")

    # Annex III høy-risiko-klasse (om relevant; NULL for limited/minimal risk)
    annex_iii_class: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Krav om menneskelig overstyring (Article 22 rett til forklaring)
    requires_human_oversight: Mapped[bool] = mapped_column(nullable=False, default=True)

    # Tidspunkt for AI-beslutning
    decision_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Rådata — strukturert LLM-output for revisjon og etterprøving
    raw_extraction_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_ai_decision_records_model_id", "model_id"),
        Index("ix_ai_decision_records_eu_ai_act_category", "eu_ai_act_category"),
    )
