"""Pydantic-skjemaer for eksportkontroll-API-et (Vareliste I/II)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.invoice import InvoiceDirection, InvoiceStatus
from app.schemas.invoice import ExportControlCheck


class ExportControlInvoiceItem(BaseModel):
    """Ett fakturafunn i den globale eksportkontroll-arbeidslista."""

    invoice_id: uuid.UUID
    invoice_number: str | None
    original_filename: str | None
    direction: InvoiceDirection
    status: InvoiceStatus
    compliance_score: str | None
    destination_country: str | None
    invoice_date: date | None
    created_at: datetime
    check: ExportControlCheck


class ExportControlListResponse(BaseModel):
    """Resultat for arbeidslista over fakturaer med listematch."""

    total_scanned: int
    total_flagged: int
    limit: int
    offset: int
    items: list[ExportControlInvoiceItem]


class ExportControlReferenceItem(BaseModel):
    """Ett punkt i den importerte referanselista."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    list_code: str
    category: str
    group: str | None
    item_code: str
    title: str | None
    regime: str | None
    source_version: str


class ExportControlReferenceResponse(BaseModel):
    total: int
    item_count_total: int   # totalt antall importerte punkter (for "lista lastet?"-indikator)
    items: list[ExportControlReferenceItem]


class ExportControlClassifyResponse(BaseModel):
    input: str
    normalized_code: str
    list_code: str
    category: str
    group: str | None
    category_title_no: str | None
    category_title_en: str | None
    regime: str | None


class ExportControlBackfillResponse(BaseModel):
    processed: int
    flagged: int
    rescored: int
