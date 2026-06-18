"""Catch-all-API — sluttbruker-/sluttbruk-screening (tredje ben i eksportkontroll).

Endepunkter:
  GET  /catch-all/invoices  — arbeidsliste over fakturaer med sluttbrukerrisiko
  POST /catch-all/backfill  — beregn status for historiske fakturaer (admin)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.database import SessionDep
from app.core.security import require_roles
from app.schemas.catch_all import (
    CatchAllBackfillResponse,
    CatchAllInvoiceItem,
    CatchAllListResponse,
)
from app.schemas.invoice import CatchAllCheck
from app.services import catch_all_service as ca_svc

router = APIRouter()


@router.get("/invoices", response_model=CatchAllListResponse)
async def list_catch_all_invoices(
    session: SessionDep,
    flagged_only: bool = Query(default=True, description="Vis kun fakturaer med signaler"),
    signal_filter: str | None = Query(
        default=None, description="Filtrer på signaltype (f.eks. 'military_end_user')"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CatchAllListResponse:
    """Arbeidsliste: fakturaer med catch-all-/sluttbrukerrisiko."""
    results, invoices, total_flagged, total_scanned = await ca_svc.list_catch_all_invoices(
        session,
        limit=limit,
        offset=offset,
        flagged_only=flagged_only,
        signal_filter=signal_filter,
    )
    items = [
        CatchAllInvoiceItem(
            invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            original_filename=inv.original_filename,
            direction=inv.direction,
            status=inv.status,
            compliance_score=inv.compliance_score.value if inv.compliance_score else None,
            destination_country=inv.destination_country,
            invoice_date=inv.invoice_date,
            created_at=inv.created_at,
            check=CatchAllCheck.model_validate(res.to_dict()),
        )
        for res, inv in zip(results, invoices, strict=True)
    ]
    return CatchAllListResponse(
        total_scanned=total_scanned,
        total_flagged=total_flagged,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.post("/backfill", response_model=CatchAllBackfillResponse)
async def backfill_catch_all(
    session: SessionDep,
    rescore: bool = Query(default=True),
    _actor=Depends(require_roles("admin")),
) -> CatchAllBackfillResponse:
    """Backfill catch-all-status for fakturaer screenet før funksjonen fantes. Admin-only."""
    result = await ca_svc.backfill_catch_all(session, rescore=rescore)
    return CatchAllBackfillResponse(**result)
