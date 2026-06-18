"""AI Governance API — logg over AI-beslutninger for EU AI Act-sporbarhet."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.core.database import SessionDep
from app.schemas.ai_governance import AIDecisionRecordListResponse, AIDecisionRecordOut
from app.services import ai_governance_service

router = APIRouter()


@router.get("", response_model=AIDecisionRecordListResponse)
async def list_ai_records(
    session: SessionDep,
    eu_ai_act_category: str | None = Query(
        default=None,
        description="Filtrer på EU AI Act-kategori ('minimal_risk' | 'limited_risk' | 'high_risk')",
    ),
    model_id: str | None = Query(default=None, description="Filtrer på modell-ID"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AIDecisionRecordListResponse:
    """List AI-beslutningsposter, nyeste først."""
    records, total = await ai_governance_service.list_records(
        session,
        eu_ai_act_category=eu_ai_act_category,
        model_id=model_id,
        limit=limit,
        offset=offset,
    )
    return AIDecisionRecordListResponse(
        total=total,
        items=[AIDecisionRecordOut.model_validate(r) for r in records],
    )


@router.get("/summary")
async def governance_summary(session: SessionDep) -> dict:
    """Aggregert oversikt for EU AI Act-rapportering (Article 52)."""
    return await ai_governance_service.governance_summary(session)


@router.get("/invoice/{invoice_id}", response_model=AIDecisionRecordOut)
async def get_record_for_invoice(invoice_id: uuid.UUID, session: SessionDep) -> AIDecisionRecordOut:
    """Hent AI-beslutningspost for én spesifikk invoice."""
    record = await ai_governance_service.get_record(session, invoice_id)
    if not record:
        raise HTTPException(status_code=404, detail="Ingen AI-beslutningspost funnet for denne invoicen")
    return AIDecisionRecordOut.model_validate(record)
