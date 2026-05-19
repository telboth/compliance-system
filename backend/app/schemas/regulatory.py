"""Pydantic-skjemaer for Regulatorisk Radar."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RegulatoryAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    feed_url: str
    title: str
    link: str | None
    summary: str | None
    published_at: datetime | None
    fetched_at: datetime
    guid: str
    severity: str
    category: str | None
    is_notified: bool
    created_at: datetime


class RegulatoryAlertListResponse(BaseModel):
    total: int
    items: list[RegulatoryAlertOut]


class RegulatorySourceOut(BaseModel):
    name: str
    feed_url: str
    category: str
    description: str
