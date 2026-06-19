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
    enabled: bool
    source_type: str
    status_note: str | None = None
    status: str
    alert_count: int
    latest_alert_at: datetime | None = None


class RegulatoryRefreshSourceOut(BaseModel):
    name: str
    feed_url: str
    category: str
    description: str
    enabled: bool
    source_type: str
    status_note: str | None = None
    result_status: str
    new_alerts: int
    message: str | None = None


class RegulatoryRefreshResponse(BaseModel):
    new_alerts_by_source: dict[str, int]
    total_new: int
    notifications_sent: int
    sources: list[RegulatoryRefreshSourceOut]
