"""Intern sperreliste-tjeneste.

Sjekker entiteter mot den interne sperrelisten ved screening.
Støtter fire typer oppføringer:
  - name: eksakt (case-insensitiv) navnetreff
  - email_domain: domene-treff i e-postadresser
  - country: landkode (ISO-2) treff
  - regex: regulært uttrykk mot alle strenger
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.internal_watchlist import WatchlistEntry

# ── CRUD ───────────────────────────────────────────────────────────────────────


async def list_entries(
    session: AsyncSession,
    *,
    active_only: bool = True,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[WatchlistEntry], int]:
    stmt = select(WatchlistEntry)
    if active_only:
        stmt = stmt.where(WatchlistEntry.is_active == True)  # noqa: E712
    await session.execute(
        select(WatchlistEntry).where(WatchlistEntry.is_active == True)  # noqa: E712
        if active_only
        else select(WatchlistEntry)
    )
    # enkel total-count
    from sqlalchemy import func

    count_stmt = select(func.count()).select_from(WatchlistEntry)
    if active_only:
        count_stmt = count_stmt.where(WatchlistEntry.is_active == True)  # noqa: E712
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(WatchlistEntry.created_at.desc()).offset(offset).limit(limit)
    entries = list((await session.execute(stmt)).scalars().all())
    return entries, total


async def get_entry(session: AsyncSession, entry_id: uuid.UUID) -> WatchlistEntry:
    from app.core.errors import NotFoundError

    entry = await session.get(WatchlistEntry, entry_id)
    if not entry:
        raise NotFoundError(f"Watchlist-oppføring {entry_id} ikke funnet")
    return entry


async def create_entry(
    session: AsyncSession,
    *,
    entry_type: str,
    value: str,
    reason: str | None = None,
    severity: str = "red",
    added_by: str = "system",
) -> WatchlistEntry:
    _validate_entry_type(entry_type)
    _validate_severity(severity)
    entry = WatchlistEntry(
        entry_type=entry_type,
        value=value.strip(),
        reason=reason,
        severity=severity,
        added_by=added_by,
        is_active=True,
    )
    session.add(entry)
    return entry


async def update_entry(
    session: AsyncSession,
    entry_id: uuid.UUID,
    *,
    value: str | None = None,
    reason: str | None = None,
    severity: str | None = None,
    is_active: bool | None = None,
) -> WatchlistEntry:
    entry = await get_entry(session, entry_id)
    if value is not None:
        entry.value = value.strip()
    if reason is not None:
        entry.reason = reason
    if severity is not None:
        _validate_severity(severity)
        entry.severity = severity
    if is_active is not None:
        entry.is_active = is_active
    return entry


async def delete_entry(session: AsyncSession, entry_id: uuid.UUID) -> None:
    entry = await get_entry(session, entry_id)
    await session.delete(entry)


# ── Screening-integrasjon ──────────────────────────────────────────────────────


@dataclass
class WatchlistHit:
    entry_id: uuid.UUID
    entry_type: str
    value: str
    reason: str | None
    severity: str
    matched_field: str  # hva som matcha (f.eks. "entity_name", "country")
    matched_value: str  # den faktiske verdien som trigget treffet


async def check_invoice(
    session: AsyncSession,
    *,
    entity_names: list[str],
    email_addresses: list[str],
    countries: list[str],
) -> list[WatchlistHit]:
    """Sjekk mot alle aktive oppføringer i sperrelisten.

    Args:
        entity_names: Liste med entitetsnavn (importør, eksportør, etc.)
        email_addresses: E-postadresser fra fakturaen
        countries: Landkoder (ISO-2) fra fakturaen

    Returns:
        Liste med WatchlistHit for alle treff.
    """
    stmt = select(WatchlistEntry).where(WatchlistEntry.is_active == True)  # noqa: E712
    entries = list((await session.execute(stmt)).scalars().all())

    hits: list[WatchlistHit] = []

    for entry in entries:
        if entry.entry_type == "name":
            for name in entity_names:
                if name and entry.value.lower() == name.lower():
                    hits.append(
                        WatchlistHit(
                            entry_id=entry.id,
                            entry_type=entry.entry_type,
                            value=entry.value,
                            reason=entry.reason,
                            severity=entry.severity,
                            matched_field="entity_name",
                            matched_value=name,
                        )
                    )

        elif entry.entry_type == "email_domain":
            domain = entry.value.lower().lstrip("@")
            for email in email_addresses:
                if email and email.lower().endswith(f"@{domain}"):
                    hits.append(
                        WatchlistHit(
                            entry_id=entry.id,
                            entry_type=entry.entry_type,
                            value=entry.value,
                            reason=entry.reason,
                            severity=entry.severity,
                            matched_field="email",
                            matched_value=email,
                        )
                    )

        elif entry.entry_type == "country":
            for country in countries:
                if country and entry.value.upper() == country.upper():
                    hits.append(
                        WatchlistHit(
                            entry_id=entry.id,
                            entry_type=entry.entry_type,
                            value=entry.value,
                            reason=entry.reason,
                            severity=entry.severity,
                            matched_field="country",
                            matched_value=country,
                        )
                    )

        elif entry.entry_type == "regex":
            try:
                pattern = re.compile(entry.value, re.IGNORECASE)
            except re.error:
                continue
            all_strings = entity_names + email_addresses + countries
            for s in all_strings:
                if s and pattern.search(s):
                    hits.append(
                        WatchlistHit(
                            entry_id=entry.id,
                            entry_type=entry.entry_type,
                            value=entry.value,
                            reason=entry.reason,
                            severity=entry.severity,
                            matched_field="regex_match",
                            matched_value=s,
                        )
                    )

    return hits


# ── Validering ─────────────────────────────────────────────────────────────────


def _validate_entry_type(entry_type: str) -> None:
    valid = {"name", "email_domain", "country", "regex"}
    if entry_type not in valid:
        raise ValueError(f"Ugyldig entry_type '{entry_type}'. Gyldige: {valid}")


def _validate_severity(severity: str) -> None:
    valid = {"yellow", "red"}
    if severity not in valid:
        raise ValueError(f"Ugyldig severity '{severity}'. Gyldige: {valid}")
