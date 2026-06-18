"""Notification-tjeneste — oppretter og henter in-app varsler.

Varsler opprettes av pipeline-tjenestene (screening, review) og
hentes av frontend via GET /api/v1/notifications?role=<rolle>.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.notification import Notification

logger = get_logger(__name__)


async def create(
    session: AsyncSession,
    *,
    message: str,
    level: str = "info",
    invoice_id: uuid.UUID | None = None,
    target_roles: list[str],
) -> Notification:
    """Opprett et nytt varsel.

    Args:
        message:      Teksten som vises til brukeren (maks 512 tegn).
        level:        Alvorlighetsgrad — "info", "warn" eller "error".
        invoice_id:   Faktura-ID for direkte navigasjon fra varselet (valgfritt).
        target_roles: Roller som skal se varselet, f.eks. ["compliance_officer", "admin"].
    """
    notif = Notification(
        id=uuid.uuid4(),
        message=message[:512],
        level=level,
        invoice_id=invoice_id,
        target_roles=target_roles,
        created_at=datetime.now(tz=timezone.utc),
    )
    session.add(notif)
    # Ikke commit her — caller håndterer transaksjonen
    return notif


async def list_for_role(
    session: AsyncSession,
    *,
    role: str,
    limit: int = 30,
    offset: int = 0,
) -> tuple[list[Notification], int]:
    """Hent varsler for en bestemt rolle, nyeste først.

    Returns:
        (items, total) — total er antall varsler ufiltrert for denne rollen.
    """
    # JSONB @> sjekker om role finnes i target_roles.
    # target_roles=["all"] er en spesialverdi som vises til alle brukere.
    from sqlalchemy import func, cast, or_
    from sqlalchemy.dialects.postgresql import JSONB

    role_filter = or_(
        Notification.target_roles.contains(cast([role], JSONB)),
        Notification.target_roles.contains(cast(["all"], JSONB)),
    )

    count_stmt = select(func.count()).select_from(
        select(Notification.id).where(role_filter).subquery()
    )
    total: int = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        select(Notification)
        .where(role_filter)
        .order_by(desc(Notification.created_at))
        .limit(limit)
        .offset(offset)
    )
    items = list((await session.execute(stmt)).scalars().all())
    return items, total
