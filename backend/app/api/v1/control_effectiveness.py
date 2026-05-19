"""Control Effectiveness API — oversikt over godkjennings-avvik."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.database import SessionDep
from app.schemas.control import ControlDeviationListResponse, ControlDeviationOut
from app.services import control_effectiveness_service as ce_svc

router = APIRouter()


@router.get("", response_model=ControlDeviationListResponse)
async def list_deviations(
    session: SessionDep,
    deviation_type: str | None = Query(
        default=None,
        description="'approved_despite_yellow' | 'approved_despite_red'",
    ),
    is_repeat_vendor: bool | None = Query(
        default=None,
        description="Filtrer kun gjentatte leverandøravvik",
    ),
    vendor_name: str | None = Query(
        default=None,
        description="Fritekst-søk på leverandørnavn",
    ),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ControlDeviationListResponse:
    """List alle registrerte kontroll-avvik, nyeste først."""
    deviations, total = await ce_svc.list_deviations(
        session,
        deviation_type=deviation_type,
        is_repeat_vendor=is_repeat_vendor,
        vendor_name=vendor_name,
        limit=limit,
        offset=offset,
    )
    return ControlDeviationListResponse(
        total=total,
        items=[ControlDeviationOut.model_validate(d) for d in deviations],
    )
