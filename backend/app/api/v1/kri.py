"""KRI Dashboard API — Key Risk Indicators for compliance-rapportering."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.database import SessionDep
from app.services import kri_service

router = APIRouter()


@router.get("")
async def get_kri_report(
    session: SessionDep,
    months: int = Query(default=12, ge=1, le=24, description="Antall måneder bakover"),
) -> dict:
    """Hent komplett KRI-rapport med alle nøkkelrisikomålinger."""
    return await kri_service.full_kri_report(session, months=months)


@router.get("/export/csv")
async def export_kri_csv(
    session: SessionDep,
    months: int = Query(default=12, ge=1, le=24),
) -> StreamingResponse:
    """Last ned KRI-rapport som CSV-fil."""
    report = await kri_service.full_kri_report(session, months=months)
    csv_content = kri_service.kri_to_csv(report)

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=kri_rapport_{months}mnd.csv"},
    )


@router.get("/screening-hit-rate")
async def get_screening_hit_rate(
    session: SessionDep,
    months: int = Query(default=12, ge=1, le=24),
) -> dict:
    return await kri_service.screening_hit_rate(session, months=months)


@router.get("/false-positive-rate")
async def get_false_positive_rate(
    session: SessionDep,
    months: int = Query(default=12, ge=1, le=24),
) -> dict:
    return await kri_service.false_positive_rate(session, months=months)


@router.get("/avg-days-to-resolution")
async def get_avg_days_to_resolution(
    session: SessionDep,
    months: int = Query(default=12, ge=1, le=24),
) -> dict:
    return await kri_service.avg_days_to_resolution(session, months=months)


@router.get("/top-countries")
async def get_top_countries(
    session: SessionDep,
    limit: int = Query(default=10, ge=1, le=50),
    months: int = Query(default=12, ge=1, le=24),
) -> list[dict]:
    return await kri_service.top_flagged_countries(session, limit=limit, months=months)


@router.get("/top-entities")
async def get_top_entities(
    session: SessionDep,
    limit: int = Query(default=10, ge=1, le=50),
    months: int = Query(default=12, ge=1, le=24),
) -> list[dict]:
    return await kri_service.top_flagged_entities(session, limit=limit, months=months)


@router.get("/risk-exposure")
async def get_risk_exposure(session: SessionDep) -> dict:
    return await kri_service.risk_exposure_summary(session)


@router.get("/monthly-trend")
async def get_monthly_trend(
    session: SessionDep,
    months: int = Query(default=12, ge=1, le=24),
) -> list[dict]:
    return await kri_service.monthly_hit_trend(session, months=months)
