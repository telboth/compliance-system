"""Risikokvantifisering API — beregner eksponering i NOK for screened invoices."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.core.database import SessionDep
from app.models.invoice import Invoice
from app.services import risk_quantification_service as rq_svc

# Montert under /invoices — per-faktura-endepunkter
invoice_router = APIRouter()
# Montert under /risk — admin / bulk-endepunkter
admin_router = APIRouter()


class RiskExposureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    invoice_id: uuid.UUID
    total_amount: Decimal | None
    currency: str | None
    currency_rate_nok: Decimal | None
    risk_multiplier: Decimal | None
    risk_exposure_nok: Decimal | None
    risk_quantified_at: datetime | None
    compliance_score: str | None


@invoice_router.post(
    "/{invoice_id}/quantify-risk",
    response_model=RiskExposureOut,
    status_code=status.HTTP_200_OK,
)
async def quantify_risk(invoice_id: uuid.UUID, session: SessionDep) -> RiskExposureOut:
    """Beregn risikoeksponering i NOK for én invoice og lagre resultatet."""
    invoice: Invoice | None = await session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice ikke funnet")

    await rq_svc.quantify_invoice_risk(session, invoice)
    await session.commit()
    await session.refresh(invoice)

    return RiskExposureOut(
        invoice_id=invoice.id,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        currency_rate_nok=invoice.currency_rate_nok,
        risk_multiplier=invoice.risk_multiplier,
        risk_exposure_nok=invoice.risk_exposure_nok,
        risk_quantified_at=invoice.risk_quantified_at,
        compliance_score=invoice.compliance_score.value if invoice.compliance_score else None,
    )


@admin_router.post(
    "/quantify-all",
    status_code=status.HTTP_200_OK,
)
async def quantify_all(session: SessionDep) -> dict[str, int]:
    """Kjør risikokvantifisering for alle screened invoices som mangler NOK-eksponering."""
    count = await rq_svc.quantify_all_screened(session)
    await session.commit()
    return {"updated": count}
