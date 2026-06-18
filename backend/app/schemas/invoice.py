"""Skjemaer for invoice-API-et."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.invoice import ApprovalState, ComplianceScore, InvoiceDirection, InvoiceStatus


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_number: int | None
    description: str | None
    product_code: str | None
    hs_code: str | None
    eccn: str | None
    serial_number: str | None
    model_number: str | None
    country_of_origin: str | None
    quantity: str | None
    unit_of_measure: str | None
    unit_price: str | None
    total_price: str | None
    currency: str | None

    @field_validator("quantity", "unit_price", "total_price", mode="before")
    @classmethod
    def decimal_to_str(cls, v: object) -> str | None:
        """Konverter Decimal-verdier fra ORM til streng for frontend."""
        if v is None:
            return None
        return str(v)


class EntityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    entity_type: str
    country: str | None
    role: str
    address: str | None
    phone: str | None
    email: str | None
    confidence: float | None = None


class VatMismatchCheck(BaseModel):
    """Heuristisk sjekk av mulig feilregistrert VAT ved eksport."""

    sender_country: str | None
    receiver_country: str | None
    export_detected: bool
    has_vat: bool
    vat_amount: str | None
    vat_rate: str | None
    flagged: bool
    reason: str | None


class ExportControlLineHit(BaseModel):
    """Ett listematch-treff på én fakturalinje (Vareliste I/II)."""

    line_index: int
    line_description: str | None
    matched_value: str
    list_code: str  # "I" | "II"
    category: str
    category_title: str
    item_code: str | None
    confidence: str  # "high" | "medium" | "low"
    matched_via: str  # "eccn" | "hs" | "keyword"
    reason: str


class ExportControlCheck(BaseModel):
    """Samlet eksportkontroll-vurdering mot DEKSAs varelister."""

    flagged: bool
    status: str  # "clear" | "review" | "controlled"
    severity: str  # "green" | "yellow" | "red"
    destination_country: str | None
    destination_sanctioned: bool
    hits: list[ExportControlLineHit] = Field(default_factory=list)
    summary: str | None


class CatchAllSignal(BaseModel):
    """Ett røde-flagg-signal i catch-all-/sluttbrukervurderingen."""

    signal_type: str
    severity: str  # "yellow" | "red"
    title: str
    detail: str
    entity_name: str | None
    country: str | None


class CatchAllCheck(BaseModel):
    """Catch-all-vurdering: sluttbruker, sluttbruk og diversjonsrisiko."""

    flagged: bool
    status: str  # "clear" | "review" | "controlled"
    severity: str  # "green" | "yellow" | "red"
    end_user_name: str | None
    end_user_country: str | None
    destination_country: str | None
    signals: list[CatchAllSignal] = Field(default_factory=list)
    summary: str | None


class InvoiceRead(BaseModel):
    """Detaljert visning av en invoice."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str | None
    customer_id: uuid.UUID | None
    direction: InvoiceDirection
    pdf_path: str
    original_filename: str | None
    file_size_bytes: int | None
    status: InvoiceStatus
    parsing_error: str | None
    total_amount: Decimal | None
    currency: str | None
    invoice_date: date | None
    compliance_score: ComplianceScore | None
    approval_state: ApprovalState = ApprovalState.ASSESSING
    created_at: datetime
    updated_at: datetime

    # Forsendelse og transport
    incoterms: str | None = None
    transport_mode: str | None = None
    destination_country: str | None = None
    po_number: str | None = None
    comments: str | None = None

    # Instruksjoner/notater og MVA
    instructions: str | None = None
    vat_amount: Decimal | None = None
    vat_rate: str | None = None

    # LLM-ekstraksjon
    extraction_confidence: dict | None = None
    extraction_error: str | None = None
    extraction_model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_text: str | None = None

    lines: list[InvoiceLineRead] = Field(default_factory=list)
    entities: list[EntityRead] = Field(default_factory=list)
    vat_mismatch_check: VatMismatchCheck | None = None
    export_control_check: ExportControlCheck | None = None
    catch_all_check: CatchAllCheck | None = None

    # Review-beslutning
    review_decision: str | None = None
    review_reason: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_claimed_by: str | None = None
    review_claimed_at: datetime | None = None


class InvoiceSummary(BaseModel):
    """Komprimert visning brukt i lister."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str | None
    direction: InvoiceDirection
    status: InvoiceStatus
    compliance_score: ComplianceScore | None
    approval_state: ApprovalState = ApprovalState.ASSESSING
    total_amount: Decimal | None
    currency: str | None
    invoice_date: date | None
    original_filename: str | None
    created_at: datetime
    vat_note_status: str | None = None
    vat_note_text: str | None = None
    email_note_status: str | None = None
    email_note_text: str | None = None
    llm_note_preview: str | None = None
    llm_note_full: str | None = None
    export_control_status: str | None = None
    export_control_summary: str | None = None
    catch_all_status: str | None = None
    catch_all_summary: str | None = None


class VatMismatchItem(BaseModel):
    """Ett invoice-funn i global VAT-kontroll."""

    invoice_id: uuid.UUID
    invoice_number: str | None
    original_filename: str | None
    direction: InvoiceDirection
    status: InvoiceStatus
    invoice_date: date | None
    created_at: datetime
    vat_check: VatMismatchCheck


class VatMismatchListResponse(BaseModel):
    """Resultat for endpoint som sjekker mulig feilregistrert VAT."""

    total_scanned: int
    total_flagged: int
    limit: int
    offset: int
    items: list[VatMismatchItem]


class InvoiceListResponse(BaseModel):
    items: list[InvoiceSummary]
    total: int
    limit: int
    offset: int


class InvoiceUploadResponse(BaseModel):
    """Returneres umiddelbart etter opplasting. Parsing skjer asynkront i bakgrunnen.

    Polling-felt: frontend sjekker invoice.status og oppdaterer seg selv
    når status skifter fra 'parsing' til 'parsed' eller 'parsing_failed'.
    """

    invoice: InvoiceRead
    duplicate_detected: bool = False
    duplicate_of_invoice_id: uuid.UUID | None = None


class ReviewCreate(BaseModel):
    """Payload for manuell review-beslutning."""

    decision: str
    """'approved' eller 'blocked'."""
    reason: str
    """Obligatorisk begrunnelse — minimum 10 tegn."""
    rule_reference: str
    """Regelreferanse eller policy som beslutningen bygger på."""
    evidence_summary: str
    """Kort oppsummering av evidens/funn som støtter beslutningen."""
    deviation_approval: bool
    """Om beslutningen er en eksplisitt avviksgodkjenning."""

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, v: str) -> str:
        if v not in ("approved", "blocked"):
            raise ValueError("decision må være 'approved' eller 'blocked'")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v or len(v.strip()) < 10:
            raise ValueError("reason må være minst 10 tegn")
        return v.strip()

    @field_validator("rule_reference")
    @classmethod
    def validate_rule_reference(cls, v: str) -> str:
        if not v or len(v.strip()) < 3:
            raise ValueError("rule_reference må være minst 3 tegn")
        return v.strip()

    @field_validator("evidence_summary")
    @classmethod
    def validate_evidence_summary(cls, v: str) -> str:
        if not v or len(v.strip()) < 10:
            raise ValueError("evidence_summary må være minst 10 tegn")
        return v.strip()


class RiskEscalationCreate(BaseModel):
    """Payload for manuell eskalering av risikonivå (controller -> review-kø)."""

    target_score: str
    """Må være 'yellow' eller 'red'."""
    reason: str
    """Obligatorisk begrunnelse — minimum 10 tegn."""

    @field_validator("target_score")
    @classmethod
    def validate_target_score(cls, v: str) -> str:
        if v not in ("yellow", "red"):
            raise ValueError("target_score må være 'yellow' eller 'red'")
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        if not v or len(v.strip()) < 10:
            raise ValueError("reason må være minst 10 tegn")
        return v.strip()


class ReviewQueueItem(BaseModel):
    """Komprimert visning for review-køen."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_number: str | None
    original_filename: str | None
    direction: InvoiceDirection
    status: InvoiceStatus
    compliance_score: ComplianceScore | None
    total_amount: Decimal | None
    currency: str | None
    destination_country: str | None
    created_at: datetime
    review_decision: str | None = None
    reviewed_at: datetime | None = None
    has_sanctions_hit: bool = False
    has_embargo_hit: bool = False
    has_ownership_risk: bool = False
    has_dual_use_risk: bool = False
    has_vat_deviation: bool = False
    has_export_control: bool = False
    has_catch_all: bool = False
    awaiting_approval: bool = False
    vat_check: VatMismatchCheck | None = None
    export_control_check: ExportControlCheck | None = None
    catch_all_check: CatchAllCheck | None = None
    review_claimed_by: str | None = None
    review_claimed_at: datetime | None = None
    claim_is_mine: bool = False
    claim_is_stale: bool = False


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int


class ReviewAndNextResponse(BaseModel):
    invoice: InvoiceRead
    next_invoice_id: uuid.UUID | None = None


class InvoiceListPreferences(BaseModel):
    table_col_widths: dict[str, int] = Field(default_factory=dict)
    table_col_presets: list[dict] = Field(default_factory=list)
    default_filters: dict[str, str | int | None] = Field(default_factory=dict)
    updated_at: datetime | None = None


class InvoiceListPreferencesUpdate(BaseModel):
    table_col_widths: dict[str, int] | None = None
    table_col_presets: list[dict] | None = None
    default_filters: dict[str, str | int | None] | None = None


class InvoiceFieldsUpdate(BaseModel):
    """Delvis oppdatering av invoice-headerfelt (manuell korrigering).

    Kun felt som er eksplisitt angitt i request-body oppdateres.
    Felt som er None / utelatt røres ikke.
    """

    invoice_number: str | None = None
    invoice_date: date | None = None
    total_amount: str | None = None  # Streng → Decimal i service
    currency: str | None = None
    incoterms: str | None = None
    transport_mode: str | None = None
    destination_country: str | None = None
    po_number: str | None = None
    comments: str | None = None
    instructions: str | None = None
    vat_amount: str | None = None  # Streng → Decimal i service
    vat_rate: str | None = None

    @field_validator("total_amount", mode="before")
    @classmethod
    def validate_total_amount(cls, v: object) -> str | None:
        """Valider at total_amount er et gyldig desimaltall."""
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        # Tillat tall med komma (europeisk) eller punktum (engelsk) som desimaltegn,
        # samt negativt fortegn og mellomrom/nbsp som tusenskilletegn.
        cleaned = re.sub(r"[\s\xa0]", "", s).replace(",", ".")
        # Fjern eventuelle valutasymboler foran/bak tallet
        cleaned = re.sub(r"^[^\d\-]+", "", cleaned)
        cleaned = re.sub(r"[^\d.]+$", "", cleaned)
        try:
            Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError(f"total_amount må være et gyldig tall, fikk: '{v}'") from exc
        return cleaned


class InvoiceLineUpdate(BaseModel):
    """Delvis oppdatering av en invoice-linje (manuell korrigering)."""

    description: str | None = None
    product_code: str | None = None
    hs_code: str | None = None
    eccn: str | None = None
    serial_number: str | None = None
    model_number: str | None = None
    country_of_origin: str | None = None
    quantity: str | None = None
    unit_of_measure: str | None = None
    unit_price: str | None = None
    total_price: str | None = None
    currency: str | None = None


class EntityUpdate(BaseModel):
    """Delvis oppdatering av en entitet (manuell korrigering)."""

    name: str | None = None
    role: str | None = None
    entity_type: str | None = None
    country: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None


class ExtractionRequest(BaseModel):
    """Request-body for POST /invoices/{id}/extract."""

    model_id: str | None = Field(
        default=None,
        description="LLM-modell å bruke. None → system-standard (llm_primary_model fra Settings).",
        examples=["claude-sonnet-4-6", "gpt-4o", "llama3.1:8b"],
    )


class ExtractionResponse(BaseModel):
    """Returneres etter LLM-ekstraksjon."""

    invoice: InvoiceRead
    overall_confidence: float
    low_confidence_fields: list[str]
    model_id: str
    input_tokens: int
    output_tokens: int
