"""Pydantic-skjemaer for Audit Plan Management."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditPlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    owner: str
    category: str
    frequency_days: int
    next_due_date: date
    last_completed_at: datetime | None
    last_completed_by: str | None
    last_completion_notes: str | None
    is_active: bool
    is_overdue: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_with_overdue(cls, plan: object) -> AuditPlanOut:
        out = cls.model_validate(plan)
        out.is_overdue = plan.next_due_date < date.today()  # type: ignore[attr-defined]
        return out

    # Placeholder — settes av from_orm_with_overdue
    is_overdue: bool = False


class AuditPlanListResponse(BaseModel):
    total: int
    items: list[AuditPlanOut]


class AuditPlanCreate(BaseModel):
    title: str = Field(..., max_length=256)
    description: str | None = None
    owner: str = Field(..., max_length=128)
    category: str = Field(..., max_length=64)
    frequency_days: int = Field(..., ge=1)
    next_due_date: date


class AuditPlanUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    description: str | None = None
    owner: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    frequency_days: int | None = Field(default=None, ge=1)
    next_due_date: date | None = None
    is_active: bool | None = None


class AuditPlanCompleteRequest(BaseModel):
    completed_by: str = Field(..., max_length=128)
    notes: str | None = None
