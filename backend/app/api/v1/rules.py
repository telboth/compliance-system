"""Regelmotor-API — CRUD og test-evaluering av YAML-regler."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session, SessionDep
from app.core.errors import NotFoundError
from app.services import rule_engine_service as re_svc
from app.services.rule_engine_service import RuleResult

router = APIRouter()


# ── Pydantic-skjemaer ──────────────────────────────────────────────────────────


class RuleVersionOut(BaseModel):
    id: uuid.UUID
    version: int
    rule_yaml: str
    created_by: str
    created_at: datetime
    comment: str | None

    model_config = {"from_attributes": True}


class RuleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    severity: str
    is_active: bool
    active_version: int
    versions: list[RuleVersionOut]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RuleCreate(BaseModel):
    name: str
    description: str | None = None
    severity: str = "yellow"
    rule_yaml: str
    comment: str | None = None


class RuleUpdate(BaseModel):
    rule_yaml: str
    name: str | None = None
    description: str | None = None
    severity: str | None = None
    comment: str | None = None


class RuleTestRequest(BaseModel):
    """Test en YAML-regel mot oppgitte felt uten å lagre den."""
    rule_yaml: str
    context: dict[str, Any]


class RuleTestResponse(BaseModel):
    triggered: bool
    error: str | None = None


class RuleEvalResponse(BaseModel):
    rule_id: uuid.UUID
    rule_name: str
    version: int
    severity: str
    triggered: bool
    description: str | None


# ── Endepunkter ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[RuleOut])
async def list_rules(session: AsyncSession = Depends(get_session)) -> list[RuleOut]:
    rules = await re_svc.list_rules(session)
    return [RuleOut.model_validate(r) for r in rules]


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    try:
        rule = await re_svc.create_rule(
            session,
            name=body.name,
            description=body.description,
            severity=body.severity,
            yaml_text=body.rule_yaml,
            comment=body.comment,
        )
        await session.commit()
        await session.refresh(rule)
        return RuleOut.model_validate(rule)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    try:
        rule = await re_svc.get_rule(session, rule_id)
        return RuleOut.model_validate(rule)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    try:
        rule = await re_svc.update_rule(
            session,
            rule_id,
            yaml_text=body.rule_yaml,
            name=body.name,
            description=body.description,
            severity=body.severity,
            comment=body.comment,
        )
        await session.commit()
        await session.refresh(rule)
        return RuleOut.model_validate(rule)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/{rule_id}/toggle", response_model=RuleOut)
async def toggle_rule(
    rule_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> RuleOut:
    """Skru av/på en regel."""
    try:
        rule = await re_svc.get_rule(session, rule_id)
        rule.is_active = not rule.is_active
        await session.commit()
        await session.refresh(rule)
        return RuleOut.model_validate(rule)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/test", response_model=RuleTestResponse)
async def test_rule(body: RuleTestRequest) -> RuleTestResponse:
    """Test en YAML-regel mot en inline-kontekst uten å lagre.

    Nyttig for å validere nye regler i editoren.
    """
    try:
        defn = re_svc.parse_rule_yaml(body.rule_yaml)
        conditions = defn.get("conditions", {})
        # Bygg minimalt context-objekt
        import dataclasses
        ctx = re_svc.InvoiceContext(
            invoice_id=uuid.uuid4(),
            destination_country=body.context.get("destination_country"),
            compliance_score=body.context.get("compliance_score"),
            currency=body.context.get("currency"),
            total_amount=body.context.get("total_amount"),
            invoice_number=body.context.get("invoice_number"),
            direction=body.context.get("direction"),
            status=body.context.get("status"),
            incoterms=body.context.get("incoterms"),
            entities=body.context.get("entities", []),
            lines=body.context.get("lines", []),
        )
        triggered = re_svc._evaluate_node(conditions, ctx)
        return RuleTestResponse(triggered=triggered)
    except Exception as exc:
        return RuleTestResponse(triggered=False, error=str(exc))


class RerunResponse(BaseModel):
    evaluated: int
    score_changed: int
    details: list[dict]


@router.post(
    "/rerun",
    response_model=RerunResponse,
    summary="Re-evaluer alle aktive regler mot eksisterende fakturaer",
)
async def rerun_rules(
    session: SessionDep,
    limit: int = Query(default=500, ge=1, le=2000, description="Maks antall fakturaer å evaluere"),
) -> RerunResponse:
    """Kjør alle aktive YAML-regler mot screened/approved/blocked-fakturaer.

    Compliance-score eskaleres hvis regelresultatet er verre enn nåværende
    (de-eskalering skjer ikke — yente-treff skal ikke overskrives).

    Returnerer antall evaluerte fakturaer og antall med endret score.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.invoice import Invoice, InvoiceStatus, ComplianceScore
    from app.models.entity import Entity
    from app.models.invoice_line import InvoiceLine
    from app.services import audit_service

    _SEVERITY_ORDER = {"green": 0, "yellow": 1, "red": 2}
    _SCORE_FROM_SEV = {"green": ComplianceScore.GREEN, "yellow": ComplianceScore.YELLOW, "red": ComplianceScore.RED}

    stmt = (
        select(Invoice)
        .where(
            Invoice.status.in_([
                InvoiceStatus.SCREENED,
                InvoiceStatus.APPROVED,
                InvoiceStatus.BLOCKED,
                InvoiceStatus.EXTRACTED,
            ])
        )
        .options(selectinload(Invoice.entities), selectinload(Invoice.lines))
        .limit(limit)
    )
    invoices = list((await session.execute(stmt)).scalars().all())

    evaluated = 0
    score_changed = 0
    details: list[dict] = []

    for invoice in invoices:
        evaluated += 1
        results = await re_svc.evaluate_invoice(
            session, invoice,
            entities=list(invoice.entities),
            lines=list(invoice.lines),
            write_audit=False,
        )
        triggered = [r for r in results if r.triggered]
        if not triggered:
            continue

        worst_sev = max((r.severity for r in triggered), key=lambda s: _SEVERITY_ORDER.get(s, 0))
        new_score = _SCORE_FROM_SEV.get(worst_sev)
        current_score = invoice.compliance_score

        current_order = _SEVERITY_ORDER.get(current_score.value if current_score else "green", 0)
        new_order = _SEVERITY_ORDER.get(worst_sev, 0)

        if new_order > current_order:
            old_val = current_score.value if current_score else "green"
            invoice.compliance_score = new_score
            await audit_service.log(
                session,
                action="rule.score_escalated",
                invoice_id=invoice.id,
                details={
                    "old_score": old_val,
                    "new_score": worst_sev,
                    "triggered_rules": [r.rule_name for r in triggered],
                },
            )
            score_changed += 1
            details.append({
                "invoice_id": str(invoice.id),
                "filename": invoice.original_filename,
                "old_score": old_val,
                "new_score": worst_sev,
            })

    await session.commit()
    return RerunResponse(evaluated=evaluated, score_changed=score_changed, details=details)
