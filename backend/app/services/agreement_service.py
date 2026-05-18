"""Rammeavtale-matching — ekstraherer vilkår og sjekker invoices mot dem.

Flyt:
  1. POST /agreements  → upload PDF, trigge LLM-ekstraksjon av vilkår
  2. GET  /agreements  → liste alle rammeavtaler
  3. POST /agreements/{id}/check/{invoice_id}  → sjekk invoice mot avtale
  4. GET  /invoices/{id}/agreement-checks  → alle sjekker for en invoice

LLM-prompting for ekstraksjon:
  Sender rå avtaletekst til LLM og ber om strukturert JSON med vilkår.
  Avvik logges i audit-loggen for sporbarhet.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.factory import get_llm_client
from app.models.agreement import Agreement, AgreementCheckResult
from app.models.invoice import Invoice
from app.services import audit_service

logger = get_logger(__name__)

# ── LLM-ekstraksjon av rammeavtalevilkår ──────────────────────────────────────

EXTRACTION_PROMPT = """\
Du er en ekspert på eksportkontroll og rammeavtaler. Analyser følgende avtaletekst og
ekstraher vilkårene som strukturert JSON.

Returner KUN gyldig JSON (ingen markdown, ingen forklaring) med dette skjemaet:
{
  "customer_names": ["<kundenavn>"],
  "allowed_countries": ["<ISO2>"] or null,
  "blocked_countries": ["<ISO2>"] or null,
  "allowed_hs_codes": ["<hs-kode>"] or null,
  "allowed_eccn": ["<eccn>"] or null,
  "max_unit_price": <tall> or null,
  "max_total_value": <tall> or null,
  "currency": "<ISO4217>" or null,
  "allowed_incoterms": ["<term>"] or null,
  "valid_from": "<YYYY-MM-DD>" or null,
  "valid_to": "<YYYY-MM-DD>" or null,
  "notes": "<eventuelle viktige kommentarer>"
}

null = ingen begrensning.

Avtaletekst:
---
{text}
---"""


async def extract_agreement_terms(
    raw_text: str,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Bruk LLM til å ekstrahere strukturerte vilkår fra avtaletekst."""
    settings = get_settings()
    mid = model_id or settings.primary_llm_model
    client = get_llm_client(mid)
    prompt = EXTRACTION_PROMPT.format(text=raw_text[:12000])  # token-grense
    response = await client.complete(prompt, max_tokens=1024)
    text = response.strip()
    # Fjern markdown code block hvis til stede
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return json.loads(text)


# ── CRUD ───────────────────────────────────────────────────────────────────────


async def create_agreement(
    session: AsyncSession,
    *,
    name: str,
    reference: str | None,
    description: str | None,
    pdf_path: str | None,
    original_filename: str | None,
    raw_text: str | None,
    model_id: str | None = None,
) -> Agreement:
    """Opprett rammeavtale og ekstraher vilkår via LLM hvis tekst er tilgjengelig."""
    agreement = Agreement(
        name=name,
        reference=reference,
        description=description,
        pdf_path=pdf_path,
        original_filename=original_filename,
    )
    session.add(agreement)
    await session.flush()

    if raw_text:
        try:
            settings = get_settings()
            mid = model_id or settings.primary_llm_model
            terms = await extract_agreement_terms(raw_text, mid)
            # Forsøk å parse datoer fra vilkårene
            agreement.valid_from = _parse_date(terms.get("valid_from"))
            agreement.valid_to = _parse_date(terms.get("valid_to"))
            agreement.extracted_terms = terms
            agreement.extraction_model = mid
            agreement.extraction_at = datetime.now(tz=timezone.utc)
            logger.info("agreement_extracted", agreement_id=str(agreement.id))
        except Exception as exc:
            logger.warning("agreement_extraction_failed", error=str(exc))
            agreement.extracted_terms = {"error": str(exc)}

    await session.flush()
    return agreement


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val))
    except ValueError:
        return None


async def list_agreements(session: AsyncSession) -> list[Agreement]:
    result = await session.execute(
        select(Agreement).order_by(Agreement.name)
    )
    return list(result.scalars().all())


async def get_agreement(session: AsyncSession, agreement_id: uuid.UUID) -> Agreement:
    result = await session.execute(
        select(Agreement)
        .where(Agreement.id == agreement_id)
        .options(selectinload(Agreement.results))
    )
    ag = result.scalar_one_or_none()
    if ag is None:
        from app.core.errors import NotFoundError
        raise NotFoundError(f"Rammeavtale {agreement_id} finnes ikke")
    return ag


# ── Matching ───────────────────────────────────────────────────────────────────


def _check_invoice_against_terms(
    invoice: Invoice,
    terms: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    """Evaluer avvik mellom en invoice og rammeavtalens vilkår.

    Returnerer (compliant, [deviations]).
    """
    deviations: list[dict[str, Any]] = []

    dest = invoice.destination_country
    # Gyldige land
    allowed_countries: list | None = terms.get("allowed_countries")
    if allowed_countries and dest and dest not in allowed_countries:
        deviations.append({
            "field": "destination_country",
            "expected": allowed_countries,
            "actual": dest,
            "message": f"Destinasjonsland {dest!r} er ikke i avtalens tillatte land",
        })

    # Blokkerte land
    blocked_countries: list | None = terms.get("blocked_countries")
    if blocked_countries and dest and dest in blocked_countries:
        deviations.append({
            "field": "destination_country",
            "expected": f"ikke {blocked_countries}",
            "actual": dest,
            "message": f"Destinasjonsland {dest!r} er eksplisitt blokkert i avtalen",
        })

    # Maksimalpris per enhet
    max_unit: float | None = terms.get("max_unit_price")
    if max_unit is not None:
        for line in invoice.lines:
            if line.unit_price and float(line.unit_price) > max_unit:
                deviations.append({
                    "field": "lines.unit_price",
                    "expected": f"<= {max_unit}",
                    "actual": float(line.unit_price),
                    "message": f"Linjepris {float(line.unit_price)} overskrider avtalens max {max_unit}",
                })

    # Total fakturabeløp
    max_total: float | None = terms.get("max_total_value")
    if max_total is not None and invoice.total_amount:
        if float(invoice.total_amount) > max_total:
            deviations.append({
                "field": "total_amount",
                "expected": f"<= {max_total}",
                "actual": float(invoice.total_amount),
                "message": f"Totalbeløp {float(invoice.total_amount)} overskrider avtalens max {max_total}",
            })

    # Valuta
    contract_currency: str | None = terms.get("currency")
    if contract_currency and invoice.currency and invoice.currency != contract_currency:
        deviations.append({
            "field": "currency",
            "expected": contract_currency,
            "actual": invoice.currency,
            "message": f"Valuta {invoice.currency!r} samsvarer ikke med avtalens {contract_currency!r}",
        })

    # Incoterms
    allowed_incoterms: list | None = terms.get("allowed_incoterms")
    if allowed_incoterms and invoice.incoterms:
        # Normaliser: sammenlign bare de første 3 tegnene
        inv_inc = invoice.incoterms[:3].upper()
        ok = any(t[:3].upper() == inv_inc for t in allowed_incoterms)
        if not ok:
            deviations.append({
                "field": "incoterms",
                "expected": allowed_incoterms,
                "actual": invoice.incoterms,
                "message": f"Incoterms {invoice.incoterms!r} er ikke i avtalens tillatte liste",
            })

    # HS-koder
    allowed_hs: list | None = terms.get("allowed_hs_codes")
    if allowed_hs:
        for line in invoice.lines:
            if line.hs_code and line.hs_code not in allowed_hs:
                deviations.append({
                    "field": "lines.hs_code",
                    "expected": allowed_hs,
                    "actual": line.hs_code,
                    "message": f"HS-kode {line.hs_code!r} er ikke i avtalens tillatte produkter",
                })

    return (len(deviations) == 0, deviations)


async def check_invoice(
    session: AsyncSession,
    agreement_id: uuid.UUID,
    invoice: Invoice,
) -> AgreementCheckResult:
    """Sjekk en invoice mot en rammeavtale og lagre resultatet."""
    from sqlalchemy.orm import selectinload as si
    ag_result = await session.execute(
        select(Agreement).where(Agreement.id == agreement_id)
    )
    agreement = ag_result.scalar_one_or_none()
    if agreement is None:
        from app.core.errors import NotFoundError
        raise NotFoundError(f"Rammeavtale {agreement_id} finnes ikke")

    terms = agreement.extracted_terms or {}
    compliant, deviations = _check_invoice_against_terms(invoice, terms)

    result = AgreementCheckResult(
        agreement_id=agreement_id,
        invoice_id=invoice.id,
        checked_at=datetime.now(tz=timezone.utc),
        compliant=compliant,
        deviations=deviations if deviations else None,
        checked_terms={
            k: terms.get(k)
            for k in ("allowed_countries", "blocked_countries", "max_unit_price",
                       "max_total_value", "currency", "allowed_incoterms", "allowed_hs_codes")
        },
    )
    session.add(result)
    await session.flush()

    # Audit-logg
    await audit_service.log(
        session,
        action="agreement.checked",
        invoice_id=invoice.id,
        details={
            "agreement_id": str(agreement_id),
            "agreement_name": agreement.name,
            "compliant": compliant,
            "deviation_count": len(deviations),
        },
    )
    logger.info(
        "agreement_check",
        agreement=agreement.name,
        invoice=str(invoice.id),
        compliant=compliant,
        deviations=len(deviations),
    )
    return result


async def get_checks_for_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
) -> list[AgreementCheckResult]:
    result = await session.execute(
        select(AgreementCheckResult)
        .where(AgreementCheckResult.invoice_id == invoice_id)
        .options(selectinload(AgreementCheckResult.agreement))
        .order_by(AgreementCheckResult.checked_at.desc())
    )
    return list(result.scalars().all())
