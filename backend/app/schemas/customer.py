"""Skjemaer for kunde-API-et."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CustomerCreate(BaseModel):
    """Request-body for å opprette en ny kunde."""

    name: str = Field(..., min_length=1, max_length=255)
    country: str | None = Field(
        default=None, max_length=2, description="ISO 3166-1 alpha-2 (f.eks. 'NO', 'DE')"
    )
    org_number: str | None = Field(default=None, max_length=32)
    risk_level: str = Field(
        default="normal",
        pattern="^(low|normal|high|critical)$",
        description="Risikonivå: low | normal | high | critical",
    )


class CustomerUpdate(BaseModel):
    """Delvis oppdatering — kun angitte felt endres."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    country: str | None = Field(default=None, max_length=2)
    org_number: str | None = None
    risk_level: str | None = Field(
        default=None,
        pattern="^(low|normal|high|critical)$",
    )


class CustomerRead(BaseModel):
    """Detaljert visning av en kunde."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    country: str | None
    org_number: str | None
    risk_level: str
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    items: list[CustomerRead]
    total: int
    limit: int
    offset: int
