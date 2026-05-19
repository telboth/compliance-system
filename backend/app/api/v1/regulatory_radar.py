"""Regulatorisk Radar API — varsler fra OFAC, EUR-Lex, HM Treasury og UN SC."""

from __future__ import annotations

from fastapi import APIRouter, Query, status

from app.core.database import SessionDep
from app.schemas.regulatory import (
    RegulatoryAlertListResponse,
    RegulatoryAlertOut,
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
async def refresh_feeds(session: SessionDep) -> dict[str, object]:
    """Hent alle konfigurerte feeds manuelt og lagre nye varsler."""
    results = await rr_svc.run_all_feeds(session)
    notified = await rr_svc.notify_unnotified(session)
    await session.commit()
    return {
        "new_alerts_by_source": results,
        "total_new": sum(results.values()),
        "notifications_sent": notified,
    }


@router.get("/sources", response_model=list[RegulatorySourceOut])
async def list_sources() -> list[RegulatorySourceOut]:
    """Returner listen over konfigurerte feed-kilder."""
    return [
        RegulatorySourceOut(
            name=feed["name"],
            feed_url=feed["feed_url"],
            category=feed["category"],
            description=feed["description"],
        )
        for feed in rr_svc.REGULATORY_FEEDS
    ]
