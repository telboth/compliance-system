"""Policy Management — CRUD med automatisk versjonering.

Regler:
- Ny policy starter med versjon 1 (is_current=True).
- Oppdatering oppretter alltid en ny versjon; ingen eksisterende versjon
  endres (immutable historikk).
- Kun én versjon per policy har is_current=True om gangen.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.compliance_policy import CompliancePolicy, CompliancePolicyVersion

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Intern hjelp
# ---------------------------------------------------------------------------


async def _next_version_number(session: AsyncSession, policy_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.max(CompliancePolicyVersion.version_number)).where(
            CompliancePolicyVersion.policy_id == policy_id
        )
    )
    current_max = result.scalar_one()
    return (current_max or 0) + 1


async def _get_policy_or_raise(
    session: AsyncSession, policy_id: uuid.UUID
) -> CompliancePolicy:
    policy = await session.get(
        CompliancePolicy,
        policy_id,
        options=[selectinload(CompliancePolicy.versions)],
    )
    if policy is None:
        raise NotFoundError(
            "Compliance-policy ikke funnet.",
            details={"policy_id": str(policy_id)},
        )
    return policy


# ---------------------------------------------------------------------------
# Offentlig API
# ---------------------------------------------------------------------------


async def create_policy(
    session: AsyncSession,
    *,
    title: str,
    category: str,
    owner: str,
    content: str,
    created_by: str,
    change_summary: str | None = None,
    law_references: list | None = None,
    effective_from: str | None = None,
) -> CompliancePolicy:
    """Opprett ny policy med initial versjon 1."""
    policy = CompliancePolicy(
        title=title[:256],
        category=category[:64],
        owner=owner[:128],
        is_active=True,
    )
    session.add(policy)
    await session.flush()  # skaff policy.id

    version = CompliancePolicyVersion(
        policy_id=policy.id,
        version_number=1,
        is_current=True,
        content=content,
        change_summary=change_summary,
        law_references=law_references,
        effective_from=effective_from,
        created_by=created_by[:128],
    )
    session.add(version)
    await session.flush()

    logger.info("policy_created", policy_id=str(policy.id), title=title)
    return policy


async def update_policy_content(
    session: AsyncSession,
    policy_id: uuid.UUID,
    *,
    content: str,
    created_by: str,
    change_summary: str | None = None,
    law_references: list | None = None,
    effective_from: str | None = None,
) -> CompliancePolicyVersion:
    """Lag ny versjon av en eksisterende policy.

    Setter is_current=False på alle eksisterende versjoner og oppretter
    en ny med forhøyet versjonsnummer.
    """
    policy = await _get_policy_or_raise(session, policy_id)

    # Sett alle eksisterende versjoner til ikke-aktive
    await session.execute(
        update(CompliancePolicyVersion)
        .where(CompliancePolicyVersion.policy_id == policy_id)
        .values(is_current=False)
    )

    next_version = await _next_version_number(session, policy_id)
    new_version = CompliancePolicyVersion(
        policy_id=policy_id,
        version_number=next_version,
        is_current=True,
        content=content,
        change_summary=change_summary,
        law_references=law_references,
        effective_from=effective_from,
        created_by=created_by[:128],
    )
    session.add(new_version)
    await session.flush()

    logger.info(
        "policy_version_created",
        policy_id=str(policy_id),
        version=next_version,
    )
    return new_version


async def update_policy_metadata(
    session: AsyncSession,
    policy_id: uuid.UUID,
    *,
    title: str | None = None,
    category: str | None = None,
    owner: str | None = None,
    is_active: bool | None = None,
) -> CompliancePolicy:
    """Oppdater metadata på hode-objektet (ingen ny versjon opprettes)."""
    policy = await _get_policy_or_raise(session, policy_id)
    if title is not None:
        policy.title = title[:256]
    if category is not None:
        policy.category = category[:64]
    if owner is not None:
        policy.owner = owner[:128]
    if is_active is not None:
        policy.is_active = is_active
    await session.flush()
    return policy


async def get_policy(
    session: AsyncSession, policy_id: uuid.UUID
) -> CompliancePolicy:
    return await _get_policy_or_raise(session, policy_id)


async def get_current_version(
    session: AsyncSession, policy_id: uuid.UUID
) -> CompliancePolicyVersion | None:
    result = await session.execute(
        select(CompliancePolicyVersion).where(
            CompliancePolicyVersion.policy_id == policy_id,
            CompliancePolicyVersion.is_current.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def list_policies(
    session: AsyncSession,
    *,
    category: str | None = None,
    is_active: bool | None = True,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CompliancePolicy], int]:
    base = select(CompliancePolicy).options(selectinload(CompliancePolicy.versions))
    if category:
        base = base.where(CompliancePolicy.category == category)
    if is_active is not None:
        base = base.where(CompliancePolicy.is_active == is_active)

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = list(
        (
            await session.execute(
                base.order_by(CompliancePolicy.category, CompliancePolicy.title)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return rows, total


async def list_versions(
    session: AsyncSession,
    policy_id: uuid.UUID,
) -> list[CompliancePolicyVersion]:
    """Returner alle versjoner for en policy, nyeste først."""
    result = await session.execute(
        select(CompliancePolicyVersion)
        .where(CompliancePolicyVersion.policy_id == policy_id)
        .order_by(CompliancePolicyVersion.version_number.desc())
    )
    return list(result.scalars().all())
