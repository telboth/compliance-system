"""Eksportkontroll-API — listematch mot DEKSAs Vareliste I og II.

Endepunkter:
  GET /export-control/invoices  — arbeidsliste over fakturaer med listematch
  GET /export-control/items     — bla i den importerte referanselista
  GET /export-control/classify  — klassifiser et enkelt kontrollnummer (ECCN/ML)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import SessionDep
from app.core.security import require_roles
from app.schemas.export_control import (
    ExportControlBackfillResponse,
    ExportControlClassifyResponse,
    ExportControlInvoiceItem,
    ExportControlListResponse,
    ExportControlReferenceItem,
    ExportControlReferenceResponse,
)
from app.schemas.invoice import ExportControlCheck
from app.services import export_control_service as ec_svc

router = APIRouter()


@router.get("/invoices", response_model=ExportControlListResponse)
async def list_export_control_invoices(
    session: SessionDep,
    flagged_only: bool = Query(default=True, description="Vis kun fakturaer med listematch"),
    list_filter: str | None = Query(default=None, description="Filtrer på vareliste ('I' | 'II')"),
    status_filter: str | None = Query(
        default=None, description="Filtrer på status ('review' | 'controlled' | 'clear')"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ExportControlListResponse:
    """Arbeidsliste: fakturaer der varer kan være listeført (Vareliste I/II)."""
    results, invoices, total_flagged, total_scanned = await ec_svc.list_export_control_invoices(
        session,
        limit=limit,
        offset=offset,
        flagged_only=flagged_only,
        list_filter=list_filter,
        status_filter=status_filter,
    )
    items = [
        ExportControlInvoiceItem(
            invoice_id=inv.id,
            invoice_number=inv.invoice_number,
            original_filename=inv.original_filename,
            direction=inv.direction,
            status=inv.status,
            compliance_score=inv.compliance_score.value if inv.compliance_score else None,
            destination_country=inv.destination_country,
            invoice_date=inv.invoice_date,
            created_at=inv.created_at,
            check=ExportControlCheck.model_validate(res.to_dict()),
        )
        for res, inv in zip(results, invoices, strict=True)
    ]
    return ExportControlListResponse(
        total_scanned=total_scanned,
        total_flagged=total_flagged,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get("/items", response_model=ExportControlReferenceResponse)
async def browse_reference_items(
    session: SessionDep,
    list_code: str | None = Query(default=None, description="Filtrer på vareliste ('I' | 'II')"),
    category: str | None = Query(default=None, description="Filtrer på kategori (ML10 / 6)"),
    search: str | None = Query(default=None, description="Søk i kontrollnummer eller tittel"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ExportControlReferenceResponse:
    """Bla i den maskinlesbart importerte varelista (referanseoppslag)."""
    rows, total = await ec_svc.browse_items(
        session,
        list_code=list_code,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )
    item_count_total = await ec_svc.count_items(session)
    return ExportControlReferenceResponse(
        total=total,
        item_count_total=item_count_total,
        items=[ExportControlReferenceItem.model_validate(r) for r in rows],
    )


@router.get("/classify", response_model=ExportControlClassifyResponse | None)
async def classify_control_code(
    code: str = Query(..., description="Kontrollnummer å klassifisere (f.eks. 6A001, ML10)"),
) -> ExportControlClassifyResponse | None:
    """Klassifiser et enkelt ECCN/ML-nummer strukturelt mot varelistene."""
    result = ec_svc.classify_code(code)
    if result is None:
        raise HTTPException(status_code=404, detail="Ikke en gjenkjennelig kontrollkode")
    return ExportControlClassifyResponse.model_validate(result)


@router.post("/backfill", response_model=ExportControlBackfillResponse)
async def backfill_export_control(
    session: SessionDep,
    rescore: bool = Query(
        default=True,
        description="Eskalér også compliance_score for fakturaer uten manuell beslutning",
    ),
    _actor=Depends(require_roles("admin")),
) -> ExportControlBackfillResponse:
    """Backfill eksportkontroll-status for fakturaer screenet før funksjonen fantes.

    Fyller arbeidslista for historiske fakturaer. Admin-only.
    """
    result = await ec_svc.backfill_export_control(session, rescore=rescore)
    return ExportControlBackfillResponse(**result)
