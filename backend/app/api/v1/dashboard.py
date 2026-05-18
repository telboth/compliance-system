"""Dashboard-API — KPI-er og statistikk for compliance-dashbordet."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.services import dashboard_service

router = APIRouter()


class DashboardResponse(BaseModel):
    generated_at: str
    totals: dict[str, Any]
    score_distribution: dict[str, int]
    status_distribution: dict[str, int]
    weekly_trend: list[dict[str, Any]]
    top_customers_with_flags: list[dict[str, Any]]
    sanctions: dict[str, Any]
    recent_audit_actions: list[dict[str, Any]]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    session: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    """Hent KPI-dashboard for compliance-offiseren."""
    data = await dashboard_service.get_dashboard(session)
    return DashboardResponse(**data)
