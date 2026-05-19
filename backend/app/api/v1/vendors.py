"""Vendor Register API — oversikt over leverandører og deres risikoprofil."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from app.core.database import SessionDep
from app.schemas.vendor import VendorListResponse, VendorNotesUpdate, VendorOut
from app.services import vendor_service

router = APIRouter()


@router.get("", response_model=VendorListResponse)
async def list_vendors(
    session: SessionDep,
    risk_level: str | None = Query(default=None, description="Filtrer på risikonivå ('low'|'medium'|'high'|'critical')"),
    country: str | None = Query(default=None, description="Filtrer på landkode (ISO-3166-1 alpha-2)"),
    search: str | None = Query(default=None, description="Søk på leverandørnavn"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> VendorListResponse:
    """List alle registrerte leverandører, sortert på risikonivå."""
    vendors, total = await vendor_service.list_vendors(
        session,
        risk_level=risk_level,
        country=country,
        search=search,
        limit=limit,
        offset=offset,
    )
    return VendorListResponse(
        total=total,
        items=[VendorOut.model_validate(v) for v in vendors],
    )


@router.get("/{vendor_id}", response_model=VendorOut)
async def get_vendor(vendor_id: uuid.UUID, session: SessionDep) -> VendorOut:
    """Hent detaljer for én leverandør."""
    vendor = await vendor_service.get_vendor(session, vendor_id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor ikke funnet")
    return VendorOut.model_validate(vendor)


@router.patch("/{vendor_id}/notes", response_model=VendorOut)
async def update_notes(
    vendor_id: uuid.UUID,
    body: VendorNotesUpdate,
    session: SessionDep,
) -> VendorOut:
    """Oppdater friekstnotes for en leverandør."""
    vendor = await vendor_service.update_vendor_notes(
        session, vendor_id, notes=body.notes
    )
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor ikke funnet")
    await session.commit()
    return VendorOut.model_validate(vendor)
