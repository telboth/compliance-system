"""Pydantic-skjemaer for Control Effectiveness."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ControlDeviationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    compliance_score_at_approval: str
    reviewed_by: str
    deviation_type: str
    vendor_name: str | None
    destination_country: str | None
    is_repeat_vendor: bool
    reason_summary: str | None
    created_at: datetime


class ControlDeviationListResponse(BaseModel):
    total: int
    items: list[ControlDeviationOut]
