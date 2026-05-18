"""Rammeavtale-API — opplasting, administrasjon og sjekk mot invoices."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_session
from app.core.errors import NotFoundError
from app.models.invoice import Invoice
from app.services import agreement_service as ag_svc
from app.services import file_storage

router = APIRouter()
invoice_check_router = APIRouter()  # montert under /invoices


# ── Skjemaer ───────────────────────────────────────────────────────────────────


class AgreementCheckOut(BaseModel):
    id: uuid.UUID
    agreement_id: uuid.UUID
    invoice_id: uuid.UUID
    checked_at: datetime
    compliant: bool
    deviations: list[dict[str, Any]] | None
    checked_terms: dict[str, Any] | None

    model_config = {"from_attributes": True}


class AgreementOut(BaseModel):
    id: uuid.UUID
    name: str
    reference: str | None
    description: str | None
    original_filename: str | None
    valid_from: date | None
    valid_to: date | None
    is_active: bool
    extracted_terms: dict[str, Any] | None
    extraction_model: str | None
    extraction_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgreementCheckRequest(BaseModel):
    invoice_id: uuid.UUID


# ── Endepunkter ────────────────────────────────────────────────────────────────


@router.get("", response_model=list[AgreementOut])
async def list_agreements(
    session: AsyncSession = Depends(get_session),
) -> list[AgreementOut]:
    agreements = await ag_svc.list_agreements(session)
    return [AgreementOut.model_validate(a) for a in agreements]


@router.post("", response_model=AgreementOut, status_code=status.HTTP_201_CREATED)
async def create_agreement(
    name: str = Form(...),
    reference: str | None = Form(None),
    description: str | None = Form(None),
    file: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
) -> AgreementOut:
    """Last opp rammeavtale (valgfri PDF) og ekstraher vilkår via LLM."""
    pdf_path = None
    original_filename = None
    raw_text: str | None = None

    if file and file.filename:
        original_filename = file.filename
        try:
            from app.parsers import parse_pdf
            pdf_path, _, _ = await file_storage.save_upload(file)
            # Forsøk å parse tekst fra PDF
            try:
                raw_text = await parse_pdf(str(pdf_path))
            except Exception:
                raw_text = None
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Kunne ikke lese fil: {exc}") from exc

    try:
        agreement = await ag_svc.create_agreement(
            session,
            name=name,
            reference=reference,
            description=description,
            pdf_path=str(pdf_path) if pdf_path else None,
            original_filename=original_filename,
            raw_text=raw_text,
        )
        await session.commit()
        await session.refresh(agreement)
        return AgreementOut.model_validate(agreement)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{agreement_id}", response_model=AgreementOut)
async def get_agreement(
    agreement_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> AgreementOut:
    try:
        ag = await ag_svc.get_agreement(session, agreement_id)
        return AgreementOut.model_validate(ag)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{agreement_id}/check", response_model=AgreementCheckOut)
async def check_invoice_against_agreement(
    agreement_id: uuid.UUID,
    body: AgreementCheckRequest,
    session: AsyncSession = Depends(get_session),
) -> AgreementCheckOut:
    """Kjør rammeavtalesjekk for en spesifikk invoice."""
    # Hent invoice med linjer og entiteter
    result = await session.execute(
        select(Invoice)
        .where(Invoice.id == body.invoice_id)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.entities),
        )
    )
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail=f"Invoice {body.invoice_id} finnes ikke")

    try:
        check = await ag_svc.check_invoice(session, agreement_id, invoice)
        await session.commit()
        return AgreementCheckOut.model_validate(check)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{agreement_id}/checks", response_model=list[AgreementCheckOut])
async def list_agreement_checks(
    agreement_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[AgreementCheckOut]:
    """List alle sjekker gjort mot en rammeavtale."""
    from app.models.agreement import AgreementCheckResult
    result = await session.execute(
        select(AgreementCheckResult)
        .where(AgreementCheckResult.agreement_id == agreement_id)
        .order_by(AgreementCheckResult.checked_at.desc())
    )
    return [AgreementCheckOut.model_validate(r) for r in result.scalars().all()]


# ── Invoice-sentriske endepunkter (montert under /invoices) ───────────────────


@invoice_check_router.get(
    "/{invoice_id}/agreement-checks",
    response_model=list[AgreementCheckOut],
)
async def get_agreement_checks_for_invoice(
    invoice_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[AgreementCheckOut]:
    checks = await ag_svc.get_checks_for_invoice(session, invoice_id)
    return [AgreementCheckOut.model_validate(c) for c in checks]
