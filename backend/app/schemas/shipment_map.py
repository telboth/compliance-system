"""Schemas for forsendelseskart."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class ShipmentMapPoint(BaseModel):
    name: str | None = None
    country: str | None = None
    address: str | None = None
    city: str | None = None
    lat: float
    lon: float
    geo_precision: str  # address | city | country


class ShipmentMapRoute(BaseModel):
    invoice_id: uuid.UUID
    invoice_number: str | None = None
    original_filename: str | None = None
    invoice_date: date | None = None
    total_amount: str | None = None
    currency: str | None = None
    compliance_score: str | None = None
    risk_level: str
    screening_hits: int
    source: ShipmentMapPoint
    destination: ShipmentMapPoint
    low_precision_line: bool


class ShipmentMapResponse(BaseModel):
    total_routes: int
    missing_location_count: int
    geocode_cache_hits: int
    geocode_external_calls: int
    items: list[ShipmentMapRoute]

