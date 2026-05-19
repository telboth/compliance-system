"""Pydantic-skjemaer for Policy Management."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LawReference(BaseModel):
    law: str
    section: str | None = None


class PolicyVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    version_number: int
    is_current: bool
    content: str
    change_summary: str | None
    law_references: list[Any] | None
    effective_from: str | None
    created_by: str
    created_at: datetime


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    category: str
    owner: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    current_version: PolicyVersionOut | None = None


class PolicyListResponse(BaseModel):
    total: int
    items: list[PolicyOut]


class PolicyCreate(BaseModel):
    title: str = Field(..., max_length=256)
    category: str = Field(..., max_length=64)
    owner: str = Field(..., max_length=128)
    content: str
    created_by: str = Field(..., max_length=128)
    change_summary: str | None = Field(default=None, max_length=512)
    law_references: list[LawReference] | None = None
    effective_from: str | None = None


class PolicyContentUpdate(BaseModel):
    content: str
    created_by: str = Field(..., max_length=128)
    change_summary: str | None = Field(default=None, max_length=512)
    law_references: list[LawReference] | None = None
    effective_from: str | None = None


class PolicyMetadataUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    category: str | None = Field(default=None, max_length=64)
    owner: str | None = Field(default=None, max_length=128)
    is_active: bool | None = None
