"""Pydantic-skjemaer for Vendor Register."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_display: str
    name_normalized: str
    country: str | None
    email_domain: str | None
    risk_level: str
    invoice_count: int
    screening_hit_count: int
    confirmed_hit_count: int
    notes: str | None
    external_id: str | None
    created_at: datetime
    updated_at: datetime


class VendorListResponse(BaseModel):
    total: int
    items: list[VendorOut]


class VendorNotesUpdate(BaseModel):
    notes: str | None = None
