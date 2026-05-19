"""Audit Plan Management API — planlagte compliance-revisjoner."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import SessionDep
from app.core.errors import NotFoundError
from app.schemas.audit_plan import (
    AuditPlanCompleteRequest,
    AuditPlanCreate,
    AuditPlanListResponse,
    AuditPlanOut,
    AuditPlanUpdate,
)
from app.services import audit_plan_service

router = APIRouter()


def _out(plan: object) -> AuditPlanOut:
    return AuditPlanOut.from_orm_with_overdue(plan)


@router.get("", response_model=AuditPlanListResponse)
async def list_audit_plans(
    session: SessionDep,
    category: str | None = Query(default=None),
    owner: str | None = Query(default=None),
    is_active: bool | None = Query(default=True),
    overdue_only: bool = Query(default=False, description="Vis kun forfalte planer"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AuditPlanListResponse:
    """List revisjonsplaner, sortert på forfallsdato (eldste først)."""
    plans, total = await audit_plan_service.list_plans(
        session,
        category=category,
        owner=owner,
        is_active=is_active,
        overdue_only=overdue_only,
        limit=limit,
        offset=offset,
    )
    return AuditPlanListResponse(
        total=total,
        items=[_out(p) for p in plans],
    )


@router.post("", response_model=AuditPlanOut, status_code=status.HTTP_201_CREATED)
async def create_audit_plan(body: AuditPlanCreate, session: SessionDep) -> AuditPlanOut:
    """Opprett en ny revisjonsplan."""
    plan = await audit_plan_service.create_plan(
        session,
        title=body.title,
        description=body.description,
        owner=body.owner,
        category=body.category,
        frequency_days=body.frequency_days,
        next_due_date=body.next_due_date,
    )
    await session.commit()
    plan = await audit_plan_service.get_plan(session, plan.id)
    return _out(plan)


@router.get("/{plan_id}", response_model=AuditPlanOut)
async def get_audit_plan(plan_id: uuid.UUID, session: SessionDep) -> AuditPlanOut:
    try:
        plan = await audit_plan_service.get_plan(session, plan_id)
        return _out(plan)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{plan_id}", response_model=AuditPlanOut)
async def update_audit_plan(
    plan_id: uuid.UUID, body: AuditPlanUpdate, session: SessionDep
) -> AuditPlanOut:
    """Oppdater metadata for en revisjonsplan."""
    try:
        plan = await audit_plan_service.update_plan(
            session,
            plan_id,
            title=body.title,
            description=body.description,
            owner=body.owner,
            category=body.category,
            frequency_days=body.frequency_days,
            next_due_date=body.next_due_date,
            is_active=body.is_active,
        )
        await session.commit()
        return _out(plan)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{plan_id}/complete", response_model=AuditPlanOut)
async def complete_audit_plan(
    plan_id: uuid.UUID, body: AuditPlanCompleteRequest, session: SessionDep
) -> AuditPlanOut:
    """Marker en revisjonsplan som fullført og rykk frem neste forfallsdato."""
    try:
        plan = await audit_plan_service.mark_completed(
            session,
            plan_id,
            completed_by=body.completed_by,
            notes=body.notes,
        )
        await session.commit()
        return _out(plan)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
