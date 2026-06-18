"""Heuristikker for VAT/MVA-kontroll."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entity import EntityRole
from app.models.invoice import Invoice

_SENDER_ROLE_PRIORITY = (EntityRole.SELLER, EntityRole.CONSIGNOR)
_RECEIVER_ROLE_PRIORITY = (
    EntityRole.BUYER,
    EntityRole.CONSIGNEE,
    EntityRole.END_USER,
    EntityRole.DELIVERY_ADDRESS,
)
_ZERO_RATE_TOKENS = {
    "0",
    "0%",
    "0.0",
    "0.00",
    "0,0",
    "0,00",
    "vat exempt",
    "exempt",
    "no vat",
    "ingen vat",
    "no mva",
    "ingen mva",
    "mva exempt",
}


@dataclass(frozen=True)
class VatMismatchCheckResult:
    sender_country: str | None
    receiver_country: str | None
    export_detected: bool
    has_vat: bool
    vat_amount: str | None
    vat_rate: str | None
    flagged: bool
    reason: str | None

    def to_dict(self) -> dict[str, str | bool | None]:
        return {
            "sender_country": self.sender_country,
            "receiver_country": self.receiver_country,
            "export_detected": self.export_detected,
            "has_vat": self.has_vat,
            "vat_amount": self.vat_amount,
            "vat_rate": self.vat_rate,
            "flagged": self.flagged,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class VatMismatchInvoiceResult:
    invoice: Invoice
    check: VatMismatchCheckResult


def _normalize_country(country: str | None) -> str | None:
    if not country:
        return None
    c = country.strip().upper()
    if not c:
        return None
    return c[:2]


def _first_country_for_roles(invoice: Invoice, roles: tuple[EntityRole, ...]) -> str | None:
    for role in roles:
        for entity in invoice.entities:
            if entity.role == role:
                normalized = _normalize_country(entity.country)
                if normalized:
                    return normalized
    return None


def _parse_rate_number(vat_rate: str) -> Decimal | None:
    cleaned = vat_rate.strip().lower().replace("%", "").replace(",", ".")
    cleaned = re.sub(r"[^0-9.\-]+", "", cleaned)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _has_vat(vat_amount: Decimal | None, vat_rate: str | None) -> bool:
    if vat_amount is not None and vat_amount > 0:
        return True

    if not vat_rate:
        return False

    normalized = vat_rate.strip().lower()
    if normalized in _ZERO_RATE_TOKENS:
        return False

    numeric = _parse_rate_number(vat_rate)
    if numeric is not None:
        return numeric > 0

    # Ukjent tekstlig sats tolkes konservativt som at VAT er brukt.
    return True


def evaluate_invoice_vat_mismatch(invoice: Invoice) -> VatMismatchCheckResult:
    """Heuristisk regel: eksport (avsender != mottaker) skal normalt ikke ha VAT."""
    sender_country = _first_country_for_roles(invoice, _SENDER_ROLE_PRIORITY)
    receiver_country = _first_country_for_roles(invoice, _RECEIVER_ROLE_PRIORITY)
    if receiver_country is None:
        receiver_country = _normalize_country(invoice.destination_country)

    export_detected = bool(sender_country and receiver_country and sender_country != receiver_country)
    has_vat = _has_vat(invoice.vat_amount, invoice.vat_rate)

    vat_amount_str = str(invoice.vat_amount) if invoice.vat_amount is not None else None
    vat_rate_str = invoice.vat_rate
    flagged = export_detected and has_vat

    reason: str | None = None
    if flagged:
        vat_info = f"belop={vat_amount_str or 'ukjent'}, sats={vat_rate_str or 'ukjent'}"
        reason = (
            f"Mulig feilregistrert VAT: avsenderland {sender_country} "
            f"og mottakerland {receiver_country} indikerer eksport, "
            f"men VAT er satt ({vat_info})."
        )

    return VatMismatchCheckResult(
        sender_country=sender_country,
        receiver_country=receiver_country,
        export_detected=export_detected,
        has_vat=has_vat,
        vat_amount=vat_amount_str,
        vat_rate=vat_rate_str,
        flagged=flagged,
        reason=reason,
    )


async def list_vat_mismatch_invoices(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
    flagged_only: bool = True,
) -> tuple[list[VatMismatchInvoiceResult], int, int]:
    """Hent invoices med VAT-heuristikk, valgfritt filtrert til kun flaggede.

    Vi evaluerer på invoice-feltene og entitetene som faktisk er lagret,
    i stedet for å stole på en separat statuskolonne som kan være utdatert.
    """
    stmt = select(Invoice).options(selectinload(Invoice.entities)).order_by(Invoice.created_at.desc())
    invoices = list((await session.execute(stmt)).scalars().all())

    results = [VatMismatchInvoiceResult(invoice=inv, check=evaluate_invoice_vat_mismatch(inv)) for inv in invoices]
    total_scanned = len(results)
    flagged_results = [result for result in results if result.check.flagged]
    total_flagged = len(flagged_results)

    paged_results = flagged_results if flagged_only else results
    return paged_results[offset : offset + limit], total_flagged, total_scanned
