"""Regulatorisk Radar API — varsler og kildestatus for regulatoriske feeds."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.core.database import SessionDep
from app.schemas.regulatory import (
    RegulatoryAlertListResponse,
    RegulatoryAlertOut,
    RegulatoryRefreshResponse,
    RegulatoryRefreshSourceOut,
    RegulatorySourceOut,
)
from app.services import regulatory_radar_service as rr_svc

router = APIRouter()


@router.get("/alerts", response_model=RegulatoryAlertListResponse)
async def list_alerts(
    session: SessionDep,
    source: str | None = Query(default=None, description="Filtrer på kilde (f.eks. 'OFAC')"),
    severity: str | None = Query(default=None, description="Filtrer på alvorlighetsgrad ('info' | 'critical')"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> RegulatoryAlertListResponse:
    """List regulatoriske varsler, nyeste først."""
    alerts, total = await rr_svc.list_alerts(
        session,
        source=source,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return RegulatoryAlertListResponse(
        total=total,
        items=[RegulatoryAlertOut.model_validate(a) for a in alerts],
    )


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def refresh_feeds(session: SessionDep) -> RegulatoryRefreshResponse:
    """Hent alle konfigurerte kilder manuelt og lagre nye varsler."""
    results = await rr_svc.refresh_sources(session)
    notified = await rr_svc.notify_unnotified(session)
    await session.commit()
    return RegulatoryRefreshResponse(
        new_alerts_by_source={result["name"]: result["new_alerts"] for result in results},
        total_new=sum(result["new_alerts"] for result in results),
        notifications_sent=notified,
        sources=[RegulatoryRefreshSourceOut.model_validate(result) for result in results],
    )


@router.get("/sources", response_model=list[RegulatorySourceOut])
async def list_sources(session: SessionDep) -> list[RegulatorySourceOut]:
    """Returner listen over konfigurerte kilder med status og metadata."""
    sources = await rr_svc.list_sources(session)
    return [RegulatorySourceOut.model_validate(source) for source in sources]
