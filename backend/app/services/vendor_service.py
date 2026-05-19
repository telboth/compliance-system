"""Vendor Register — tjeneste for opprettelse og oppdatering av leverandørposter.

Kalles fra screening_service etter at en screening er fullført, for å holde
leverandørregisteret oppdatert med siste risikoinformasjon.
"""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.screening import MatchStatus
from app.models.vendor import Vendor

logger = get_logger(__name__)


def _normalize_name(name: str) -> str:
    """Normaliser leverandørnavn for deduplisering."""
    return re.sub(r"\s+", " ", name.strip().lower())


def _email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].lower().strip()


def _risk_level(confirmed_hits: int, screening_hits: int, invoice_count: int) -> str:
    """Beregn risikonivå basert på historikk."""
    if confirmed_hits > 0:
        return "critical"
    if screening_hits >= 3:
        return "high"
    rate = screening_hits / max(invoice_count, 1)
    if rate >= 0.5:
        return "high"
    if screening_hits >= 1 or rate >= 0.2:
        return "medium"
    return "low"


async def get_or_create_vendor(
    session: AsyncSession,
    *,
    name: str,
    country: str | None = None,
    email: str | None = None,
) -> Vendor:
    """Hent eksisterende vendor eller opprett ny.

    Nøkkel er normalisert navn + land.  Oppdaterer `name_display` og
    `email_domain` om de har endret seg.
    """
    name_norm = _normalize_name(name)
    stmt = select(Vendor).where(
        Vendor.name_normalized == name_norm,
        Vendor.country == country,
    )
    vendor = (await session.execute(stmt)).scalars().first()

    if vendor is None:
        vendor = Vendor(
            name_normalized=name_norm,
            name_display=name[:512],
            country=country,
            email_domain=_email_domain(email),
            risk_level="low",
            invoice_count=0,
            screening_hit_count=0,
            confirmed_hit_count=0,
        )
        session.add(vendor)
        await session.flush()
        logger.info("vendor_created", name=name_norm, country=country)
    else:
        # Oppdater visningsnavn og e-postdomene om det har endret seg
        vendor.name_display = name[:512]
        if email:
            vendor.email_domain = _email_domain(email)

    return vendor


async def record_screening_outcome(
    session: AsyncSession,
    *,
    vendor: Vendor,
    worst_status: MatchStatus,
) -> None:
    """Oppdater risikostatistikk etter én screening av denne leverandøren."""
    vendor.invoice_count += 1
    if worst_status in (MatchStatus.CONFIRMED_MATCH, MatchStatus.POTENTIAL_MATCH):
        vendor.screening_hit_count += 1
    if worst_status == MatchStatus.CONFIRMED_MATCH:
        vendor.confirmed_hit_count += 1

    vendor.risk_level = _risk_level(
        vendor.confirmed_hit_count,
        vendor.screening_hit_count,
        vendor.invoice_count,
    )


async def get_vendor(session: AsyncSession, vendor_id: uuid.UUID) -> Vendor | None:
    return await session.get(Vendor, vendor_id)


async def list_vendors(
    session: AsyncSession,
    *,
    risk_level: str | None = None,
    country: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Vendor], int]:
    """Returner (vendors, total) med valgfri filtrering."""
    base = select(Vendor)
    if risk_level:
        base = base.where(Vendor.risk_level == risk_level)
    if country:
        base = base.where(Vendor.country == country)
    if search:
        base = base.where(Vendor.name_normalized.ilike(f"%{_normalize_name(search)}%"))

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = list(
        (
            await session.execute(
                base.order_by(Vendor.risk_level.desc(), Vendor.name_normalized.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return rows, total


async def update_vendor_notes(
    session: AsyncSession,
    vendor_id: uuid.UUID,
    *,
    notes: str | None,
) -> Vendor | None:
    """Oppdater friekstnotes på en vendor."""
    vendor = await session.get(Vendor, vendor_id)
    if vendor is None:
        return None
    vendor.notes = notes
    await session.flush()
    return vendor
