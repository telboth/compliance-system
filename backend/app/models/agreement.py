"""Agreement og AgreementCheckResult — rammeavtale-matching.

En Agreement representerer en lastet rammeavtale (PDF) med LLM-ekstraherte
vilkår. AgreementCheckResult er resultatet av å matche én invoice mot
én rammeavtale — lagres for audit-spor og rapportering.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Agreement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """En rammeavtale ekstrahert fra PDF.

    Felt som customer_ids, allowed_products, max_unit_price, allowed_countries
    m.m. ekstraheres av LLM og lagres som JSONB for fleksibel matching.
    """

    __tablename__ = "agreements"

    name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Gyldighetsperiode
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # LLM-ekstraherte vilkår (fleksibel JSONB):
    # {
    #   customer_ids: [uuid, ...],
    #   customer_names: ["EuroTech Solutions GmbH", ...],
    #   allowed_countries: ["DE", "NO", ...],   # None = alle
    #   blocked_countries: ["RU", "BY", ...],
    #   allowed_hs_codes: ["9026.20.20", ...],   # None = alle
    #   allowed_eccn: ["EAR99", ...],
    #   max_unit_price: 50000,
    #   max_total_value: 500000,
    #   currency: "EUR",
    #   allowed_incoterms: ["DAP", "CIF"],
    #   notes: "..."
    # }
    extracted_terms: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    extraction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    results: Mapped[list[AgreementCheckResult]] = relationship(back_populates="agreement", cascade="all, delete-orphan")


class AgreementCheckResult(UUIDPrimaryKeyMixin, Base):
    """Resultatet av å sjekke én invoice mot én rammeavtale."""

    __tablename__ = "agreement_check_results"

    agreement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agreements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # True = ingen avvik
    compliant: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Liste av avvik:
    # [{"field": "destination_country", "expected": ["DE"], "actual": "RU",
    #   "message": "Land RU er ikke tillatt i rammeavtalen"}]
    deviations: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Hvilke vilkår ble sjekket
    checked_terms: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    agreement: Mapped[Agreement] = relationship(back_populates="results")
