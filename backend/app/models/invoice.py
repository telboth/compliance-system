"""Invoice — primærdokumentet vi analyserer."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text, event
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.entity import Entity
    from app.models.invoice_line import InvoiceLine


class InvoiceDirection(str, enum.Enum):
    """Om invoicen er innkommende (kjøp) eller utgående (salg)."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"


class InvoiceStatus(str, enum.Enum):
    """Hvor i pipeline en invoice befinner seg.

    Pipeline-rekkefølgen følger sprint-leveransene:
    uploaded → parsing → parsed → extracting → extracted →
    screening → screened (eller screening_failed) → reviewed → approved/blocked.
    """

    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSING_FAILED = "parsing_failed"
    NOT_INVOICE = "not_invoice"
    EXTRACTING = "extracting"
    EXTRACTION_FAILED = "extraction_failed"
    EXTRACTED = "extracted"
    SCREENING = "screening"
    SCREENING_FAILED = "screening_failed"
    SCREENED = "screened"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    BLOCKED = "blocked"


class ComplianceScore(str, enum.Enum):
    """Samlet utfall av alle compliance-sjekker."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class ApprovalState(str, enum.Enum):
    """Entydig godkjenningsstatus for review-flyt."""

    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"
    NOT_REQUIRED = "not_required"
    ASSESSING = "assessing"


def compute_approval_state(
    status: InvoiceStatus,
    compliance_score: ComplianceScore | None,
) -> ApprovalState:
    if status == InvoiceStatus.APPROVED:
        return ApprovalState.APPROVED
    if status == InvoiceStatus.BLOCKED:
        return ApprovalState.BLOCKED
    if compliance_score in {ComplianceScore.YELLOW, ComplianceScore.RED}:
        return ApprovalState.PENDING
    if compliance_score == ComplianceScore.GREEN:
        return ApprovalState.NOT_REQUIRED
    return ApprovalState.ASSESSING


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """En invoice (faktura) lastet inn i systemet for compliance-kontroll.

    PDF-en lagres på disk; stien beholdes her for revisor og audit-spor.
    Rå tekst kan lagres for sporbarhet under MVP — i fase 2 vil vi vurdere
    om dette skal anonymiseres eller slettes etter prosessering for å
    overholde dataminimering (GDPR Art. 5(1)(c)).
    """

    __tablename__ = "invoices"

    invoice_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    direction: Mapped[InvoiceDirection] = mapped_column(
        Enum(InvoiceDirection, name="invoice_direction", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    pdf_path: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=InvoiceStatus.UPLOADED,
        index=True,
    )
    parsing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Lagres når parsing feiler, så controlleren ser hvorfor."""

    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    compliance_score: Mapped[ComplianceScore | None] = mapped_column(
        Enum(ComplianceScore, name="compliance_score", values_callable=lambda e: [x.value for x in e]),
        nullable=True,
        index=True,
    )
    approval_state: Mapped[ApprovalState] = mapped_column(
        Enum(ApprovalState, name="approval_state", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=ApprovalState.ASSESSING,
        index=True,
    )

    # Forsendelse og transport
    incoterms: Mapped[str | None] = mapped_column(String(10), nullable=True)
    transport_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    po_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Instruksjoner/notater direkte fra dokumentet
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # MVA/moms
    vat_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    vat_rate: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vat_note_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    vat_note_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email_note_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    email_note_text: Mapped[str | None] = mapped_column(String(512), nullable=True)
    llm_note_preview: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Eksportkontroll — listematch mot Vareliste I/II (DEKSA).
    # Status: None (ikke evaluert) | "clear" | "review" | "controlled"
    export_control_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    export_control_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Catch-all — sluttbruker-/sluttbruk-screening (tredje ben i eksportkontroll).
    # Status: None (ikke evaluert) | "clear" | "review" | "controlled"
    catch_all_status: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    catch_all_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # LLM-ekstraksjon (Sprint 2)
    extraction_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Token-forbruk per ekstraksjonskjøring — brukes til kostnadssporing.
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)

    # Manuell review-beslutning (compliance officer / admin)
    review_decision: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    """'approved' eller 'blocked' — satt av review_invoice()."""
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    """Obligatorisk begrunnelse fra revieweren."""
    reviewed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    """Bruker-ID eller navn på den som fattet beslutningen."""
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    review_claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    review_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Risikokvantifisering (Feature #3)
    risk_exposure_nok: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    """Estimert eksponering i NOK = total_amount * currency_rate_nok * risk_multiplier."""
    currency_rate_nok: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    """Valutakurs mot NOK på kvantifiseringstidspunktet (fra api.frankfurter.app)."""
    risk_multiplier: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    """Risikomultiplikator basert på compliance_score (GREEN=1.0, YELLOW=1.5, RED=2.5)."""
    risk_quantified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    """Tidspunkt for siste risikokvantifisering."""

    customer: Mapped[Customer | None] = relationship(back_populates="invoices")
    lines: Mapped[list[InvoiceLine]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )
    entities: Mapped[list[Entity]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
    )


@event.listens_for(Invoice, "before_insert")
def _invoice_before_insert(_mapper: object, _connection: object, target: Invoice) -> None:
    target.approval_state = compute_approval_state(target.status, target.compliance_score)


@event.listens_for(Invoice, "before_update")
def _invoice_before_update(_mapper: object, _connection: object, target: Invoice) -> None:
    target.approval_state = compute_approval_state(target.status, target.compliance_score)
