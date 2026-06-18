"""Tjeneste for den hash-kjedede audit-loggen.

Bruk:
    await audit_service.log(
        session,
        invoice_id=invoice.id,
        action="screening.completed",
        actor="system",
        details={"score": "red", "matches": 2},
    )

SHA-256-hash beregnes over en kanonisk streng:
  <previous_hash>|<invoice_id>|<action>|<actor>|<iso_timestamp>|<details_json>

Manglende felter erstattes med tomstreng for å bevare kjede-integritet.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog

logger = get_logger(__name__)

# Sentinel: hashes for første innslag i en ny kjede
GENESIS_HASH = "0" * 64


def _compute_hash(
    *,
    previous_hash: str,
    invoice_id: str,
    action: str,
    actor: str,
    timestamp_iso: str,
    details_json: str,
) -> str:
    """SHA-256 over kanonisk pipe-separert streng."""
    raw = f"{previous_hash}|{invoice_id}|{action}|{actor}|{timestamp_iso}|{details_json}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _get_previous_hash(
    session: AsyncSession,
    invoice_id: uuid.UUID | None,
) -> str:
    """Hent current_hash for nyligste innslag i kjeden for denne invoice_id."""
    stmt = (
        select(AuditLog.current_hash)
        .where(AuditLog.invoice_id == invoice_id)
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    return row if row is not None else GENESIS_HASH


async def log(
    session: AsyncSession,
    *,
    action: str,
    actor: str = "system",
    invoice_id: uuid.UUID | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    """Opprett ett nytt audit-innslag og legg det til aktiv transaksjon.

    Kalles inne i en eksisterende database-transaksjon — ikke commit her.
    """
    now = datetime.now(tz=UTC)
    prev_hash = await _get_previous_hash(session, invoice_id)
    details_json = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
    current_hash = _compute_hash(
        previous_hash=prev_hash,
        invoice_id=str(invoice_id) if invoice_id else "",
        action=action,
        actor=actor,
        timestamp_iso=now.isoformat(),
        details_json=details_json,
    )

    entry = AuditLog(
        invoice_id=invoice_id,
        action=action,
        actor=actor,
        details=details,
        previous_hash=prev_hash if prev_hash != GENESIS_HASH else None,
        current_hash=current_hash,
        created_at=now,
    )
    session.add(entry)
    await session.flush()
    logger.debug("audit_log", action=action, actor=actor, invoice_id=str(invoice_id))
    return entry


async def get_for_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    limit: int = 200,
) -> list[AuditLog]:
    """Hent alle audit-innslag for en invoice, nyeste først."""
    stmt = select(AuditLog).where(AuditLog.invoice_id == invoice_id).order_by(AuditLog.created_at.asc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def verify_chain(
    session: AsyncSession,
    invoice_id: uuid.UUID,
) -> tuple[bool, list[str]]:
    """Sjekk at hash-kjeden er ubrutt for en invoice.

    Returnerer (ok, list_of_errors).
    """
    rows = await get_for_invoice(session, invoice_id, limit=10_000)
    errors: list[str] = []
    prev = GENESIS_HASH

    for row in rows:
        # Verifiser koblet kjede
        expected_prev = None if prev == GENESIS_HASH else prev
        if row.previous_hash != expected_prev:
            errors.append(
                f"Rad {row.id}: previous_hash mismatch (forventet {expected_prev!r}, fant {row.previous_hash!r})"
            )

        # Verifiser at current_hash stemmer
        details_json = json.dumps(row.details or {}, ensure_ascii=False, sort_keys=True)
        expected_hash = _compute_hash(
            previous_hash=prev,
            invoice_id=str(row.invoice_id) if row.invoice_id else "",
            action=row.action,
            actor=row.actor,
            timestamp_iso=row.created_at.isoformat(),
            details_json=details_json,
        )
        if row.current_hash != expected_hash:
            errors.append(f"Rad {row.id}: hash-brudd — innslaget kan ha blitt endret")

        prev = row.current_hash

    return (len(errors) == 0, errors)
