"""Forsendelses-endepunkter (kartdata)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.core.database import SessionDep
from app.schemas.shipment_map import ShipmentMapResponse
from app.services.shipment_map_service import build_shipments_map

router = APIRouter()


@router.get(
    "/map",
    response_model=ShipmentMapResponse,
    summary="Kartdata for forsendelser (avsender -> mottaker)",
)
async def get_shipments_map(
    session: SessionDep,
    limit: int = Query(200, ge=1, le=1000),
    risk: str | None = Query(
        None,
        pattern="^(low|medium|high)$",
        description="Valgfritt risikofilter.",
    ),
    date_from: date | None = Query(None, description="Opprettet fra dato (YYYY-MM-DD)."),
    date_to: date | None = Query(None, description="Opprettet til dato (YYYY-MM-DD)."),
    max_geocode_lookups: int | None = Query(
        None,
        ge=0,
        le=200,
        description="Maks antall eksterne geokodingskall for denne responsen.",
    ),
) -> ShipmentMapResponse:
    return await build_shipments_map(
        session,
        limit=limit,
        risk=risk,
        date_from=date_from,
        date_to=date_to,
        max_external_lookups=max_geocode_lookups,
    )
