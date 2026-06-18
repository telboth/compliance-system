"""Pydantic-skjemaer for catch-all-API-et (sluttbruker-screening)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.invoice import InvoiceDirection, InvoiceStatus
from app.schemas.invoice import CatchAllCheck


class CatchAllInvoiceItem(BaseModel):
    """Ett fakturafunn i catch-all-arbeidslista."""

    invoice_id: uuid.UUID
    invoice_number: str | None
    original_filename: str | None
    direction: InvoiceDirection
    status: InvoiceStatus
    compliance_score: str | None
    destination_country: str | None
    invoice_date: date | None
    created_at: datetime
    check: CatchAllCheck


class CatchAllListResponse(BaseModel):
    total_scanned: int
    total_flagged: int
    limit: int
    offset: int
    items: list[CatchAllInvoiceItem]


class CatchAllBackfillResponse(BaseModel):
    processed: int
    flagged: int
    rescored: int
