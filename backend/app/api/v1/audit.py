"""Audit-log API — lese og verifisere hash-kjedet revisjonslogg."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import NotFoundError
from app.services import audit_service

router = APIRouter()


# ── Pydantic-skjemaer ──────────────────────────────────────────────────────────


class AuditLogEntry(BaseModel):
    id: uuid.UUID
    invoice_id: uuid.UUID | None
    action: str
    actor: str
    details: dict[str, Any] | None
    previous_hash: str | None
    current_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int


class ChainVerifyResponse(BaseModel):
    ok: bool
    errors: list[str]


# ── Endepunkter ────────────────────────────────────────────────────────────────


@router.get(
    "/{invoice_id}/audit",
    response_model=AuditLogListResponse,
    summary="Hent audit-logg for en invoice",
)
async def get_audit_log(
    invoice_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> AuditLogListResponse:
    """Returner alle audit-innslag for invoice, kronologisk."""
    rows = await audit_service.get_for_invoice(session, invoice_id)
    items = [AuditLogEntry.model_validate(r) for r in rows]
    return AuditLogListResponse(items=items, total=len(items))


@router.get(
    "/{invoice_id}/audit/verify",
    response_model=ChainVerifyResponse,
    summary="Verifiser hash-kjede for en invoice",
)
async def verify_audit_chain(
    invoice_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ChainVerifyResponse:
    """Sjekk at ingen audit-innslag har blitt tampered with."""
    ok, errors = await audit_service.verify_chain(session, invoice_id)
    return ChainVerifyResponse(ok=ok, errors=errors)
