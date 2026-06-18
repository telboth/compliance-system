"""Audit Plan Management — CRUD og fremdriftslogikk for revisjonsplaner.

mark_completed() rykker frem next_due_date med frequency_days fra dagens dato,
slik at neste gjennomføring automatisk planlegges.

Overdue-status beregnes dynamisk (next_due_date < today) — ingen ekstra kolonne.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.audit_plan import AuditPlan

logger = get_logger(__name__)


async def _get_or_raise(session: AsyncSession, plan_id: uuid.UUID) -> AuditPlan:
    plan = await session.get(AuditPlan, plan_id)
    if plan is None:
        raise NotFoundError(
            "Audit-plan ikke funnet.",
            details={"plan_id": str(plan_id)},
        )
    return plan


async def create_plan(
    session: AsyncSession,
    *,
    title: str,
    description: str | None = None,
    owner: str,
    category: str,
    frequency_days: int,
    next_due_date: date,
) -> AuditPlan:
    plan = AuditPlan(
        title=title[:256],
        description=description,
        owner=owner[:128],
        category=category[:64],
        frequency_days=frequency_days,
        next_due_date=next_due_date,
        is_active=True,
    )
    session.add(plan)
    await session.flush()
    logger.info("audit_plan_created", plan_id=str(plan.id), title=title)
    return plan


async def get_plan(session: AsyncSession, plan_id: uuid.UUID) -> AuditPlan:
    return await _get_or_raise(session, plan_id)


async def list_plans(
    session: AsyncSession,
    *,
    category: str | None = None,
    owner: str | None = None,
    is_active: bool | None = True,
    overdue_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditPlan], int]:
    base = select(AuditPlan)
    if category:
        base = base.where(AuditPlan.category == category)
    if owner:
        base = base.where(AuditPlan.owner == owner)
    if is_active is not None:
        base = base.where(AuditPlan.is_active == is_active)
    if overdue_only:
        today = date.today()
        base = base.where(AuditPlan.next_due_date < today)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    rows = list(
        (await session.execute(base.order_by(AuditPlan.next_due_date.asc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return rows, total


async def update_plan(
    session: AsyncSession,
    plan_id: uuid.UUID,
    *,
    title: str | None = None,
    description: str | None = None,
    owner: str | None = None,
    category: str | None = None,
    frequency_days: int | None = None,
    next_due_date: date | None = None,
    is_active: bool | None = None,
) -> AuditPlan:
    plan = await _get_or_raise(session, plan_id)
    if title is not None:
        plan.title = title[:256]
    if description is not None:
        plan.description = description
    if owner is not None:
        plan.owner = owner[:128]
    if category is not None:
        plan.category = category[:64]
    if frequency_days is not None:
        plan.frequency_days = max(1, frequency_days)
    if next_due_date is not None:
        plan.next_due_date = next_due_date
    if is_active is not None:
        plan.is_active = is_active
    await session.flush()
    return plan


async def mark_completed(
    session: AsyncSession,
    plan_id: uuid.UUID,
    *,
    completed_by: str,
    notes: str | None = None,
) -> AuditPlan:
    """Marker et audit-plan som fullført og rykk frem neste forfallsdato.

    next_due_date = today + frequency_days
    """
    plan = await _get_or_raise(session, plan_id)
    today = date.today()
    plan.last_completed_at = datetime.now(UTC)
    plan.last_completed_by = completed_by[:128]
    plan.last_completion_notes = notes
    plan.next_due_date = today + timedelta(days=plan.frequency_days)
    await session.flush()

    logger.info(
        "audit_plan_completed",
        plan_id=str(plan_id),
        next_due=plan.next_due_date.isoformat(),
        completed_by=completed_by,
    )
    return plan
