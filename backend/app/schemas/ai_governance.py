"""Pydantic-skjemaer for AI Governance."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AIDecisionRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    model_id: str
    model_provider: str
    input_tokens: int | None
    output_tokens: int | None
    overall_confidence: float | None
    low_confidence_fields: str | None
    eu_ai_act_category: str
    annex_iii_class: str | None
    requires_human_oversight: bool
    decision_at: datetime
    raw_extraction_meta: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class AIDecisionRecordListResponse(BaseModel):
    total: int
    items: list[AIDecisionRecordOut]
