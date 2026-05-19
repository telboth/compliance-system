"""Risikokvantifisering — beregner eksponering i NOK for screened invoices.

Valutakurser hentes fra api.frankfurter.app (ECB-data) med 24-timers
TTL-cache i minnet.  Dersom API-et ikke er tilgjengelig, brukes siste
kjente kurs fra cachen (eller 1.0 som fallback).

risk_exposure_nok = total_amount * currency_rate_nok * risk_multiplier

risk_multiplier:
  GREEN  → 1.0  (lav sannsynlighet for tap)
  YELLOW → 1.5  (forhøyet usikkerhet)
  RED    → 2.5  (høy sannsynlighet for kostnad ved håndtering/blokk)
  None   → 1.0  (ukjent score → konservativ)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import ComplianceScore, Invoice, InvoiceStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valuta-cache
# ---------------------------------------------------------------------------

_RATE_CACHE: dict[str, tuple[Decimal, datetime]] = {}
_CACHE_TTL = timedelta(hours=24)
_FRANKFURTER_URL = "https://api.frankfurter.app/latest"
_BASE_CURRENCY = "NOK"

_RISK_MULTIPLIERS: dict[ComplianceScore | None, Decimal] = {
    ComplianceScore.GREEN: Decimal("1.0"),
    ComplianceScore.YELLOW: Decimal("1.5"),
    ComplianceScore.RED: Decimal("2.5"),
    None: Decimal("1.0"),
}


async def _fetch_rate_nok(currency: str, timeout: int = 10) -> Decimal | None:
    """Hent 1 enhet <currency> → NOK fra Frankfurter API."""
    if not currency or currency.upper() == _BASE_CURRENCY:
        return Decimal("1.0")

    upper = currency.upper()

    # Sjekk cache
    cached = _RATE_CACHE.get(upper)
    if cached and datetime.now(UTC) - cached[1] < _CACHE_TTL:
        return cached[0]

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                _FRANKFURTER_URL,
                params={"from": upper, "to": _BASE_CURRENCY},
            )
            resp.raise_for_status()
            data = resp.json()
            rate_raw = data.get("rates", {}).get(_BASE_CURRENCY)
            if rate_raw is None:
                logger.warning("Ingen NOK-kurs for %s i Frankfurter-svar", upper)
                return None
            rate = Decimal(str(rate_raw))
            _RATE_CACHE[upper] = (rate, datetime.now(UTC))
            logger.debug("Hentet valutakurs %s→NOK: %s", upper, rate)
            return rate
    except Exception as exc:
        logger.warning("Kunne ikke hente valutakurs for %s: %s", upper, exc)
        # Returner siste cache-verdi uavhengig av alder
        if upper in _RATE_CACHE:
            return _RATE_CACHE[upper][0]
        return None


async def quantify_invoice_risk(
    session: AsyncSession,
    invoice: Invoice,
    *,
    timeout: int = 10,
) -> Invoice:
    """Beregn og lagre risikoeksponering for én invoice.

    Setter `risk_exposure_nok`, `currency_rate_nok`, `risk_multiplier` og
    `risk_quantified_at` direkte på invoice-objektet og flusher til DB.
    Returnerer den oppdaterte invoice-instansen.
    """
    if invoice.total_amount is None:
        logger.debug("Ingen total_amount på invoice %s — hopper over kvantifisering", invoice.id)
        return invoice

    multiplier = _RISK_MULTIPLIERS.get(invoice.compliance_score, Decimal("1.0"))

    currency = (invoice.currency or "").strip().upper() or "USD"
    rate = await _fetch_rate_nok(currency, timeout=timeout)
    if rate is None:
        logger.warning("Ingen valutakurs for %s — bruker 1.0 som fallback", currency)
        rate = Decimal("1.0")

    try:
        exposure = invoice.total_amount * rate * multiplier
    except (InvalidOperation, TypeError) as exc:
        logger.warning("Risikoberegning feilet for invoice %s: %s", invoice.id, exc)
        return invoice

    invoice.risk_exposure_nok = exposure.quantize(Decimal("0.01"))
    invoice.currency_rate_nok = rate.quantize(Decimal("0.000001"))
    invoice.risk_multiplier = multiplier
    invoice.risk_quantified_at = datetime.now(UTC)
    await session.flush()
    return invoice


async def quantify_all_screened(
    session: AsyncSession,
    *,
    limit: int = 200,
    timeout: int = 10,
) -> int:
    """Kvantifiser alle screened invoices som mangler risikoeksponering.

    Returnerer antall oppdaterte rader.
    """
    stmt = (
        select(Invoice)
        .where(
            Invoice.status == InvoiceStatus.SCREENED,
            Invoice.total_amount.is_not(None),
            Invoice.risk_quantified_at.is_(None),
        )
        .limit(limit)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    count = 0
    for inv in rows:
        await quantify_invoice_risk(session, inv, timeout=timeout)
        count += 1
    if count:
        await session.flush()
    return count
