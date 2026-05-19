"""Policy Management API — CRUD for compliance-retningslinjer med versjonering."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import SessionDep
from app.core.errors import NotFoundError
from app.schemas.policy import (
    PolicyContentUpdate,
    PolicyCreate,
    PolicyListResponse,
    PolicyMetadataUpdate,
    PolicyOut,
    PolicyVersionOut,
)
from app.services import policy_service

router = APIRouter()


def _to_policy_out(policy: object, current_version: object | None = None) -> PolicyOut:
    out = PolicyOut.model_validate(policy)
    if current_version is not None:
        out.current_version = PolicyVersionOut.model_validate(current_version)
    return out


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    session: SessionDep,
    category: str | None = Query(default=None),
    is_active: bool | None = Query(default=True, description="None = vis alle"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PolicyListResponse:
    """List compliance-policies, sortert på kategori og tittel."""
    policies, total = await policy_service.list_policies(
        session, category=category, is_active=is_active, limit=limit, offset=offset
    )
    items = []
    for p in policies:
        current = next((v for v in (p.versions or []) if v.is_current), None)
        items.append(_to_policy_out(p, current))
    return PolicyListResponse(total=total, items=items)


@router.post("", response_model=PolicyOut, status_code=status.HTTP_201_CREATED)
async def create_policy(body: PolicyCreate, session: SessionDep) -> PolicyOut:
    """Opprett ny compliance-policy med initial versjon."""
    policy = await policy_service.create_policy(
        session,
        title=body.title,
        category=body.category,
        owner=body.owner,
        content=body.content,
        created_by=body.created_by,
        change_summary=body.change_summary,
        law_references=[r.model_dump() for r in body.law_references] if body.law_references else None,
        effective_from=body.effective_from,
    )
    await session.commit()
    policy = await policy_service.get_policy(session, policy.id)
    current = await policy_service.get_current_version(session, policy.id)
    return _to_policy_out(policy, current)


@router.get("/{policy_id}", response_model=PolicyOut)
async def get_policy(policy_id: uuid.UUID, session: SessionDep) -> PolicyOut:
    """Hent detaljer for én policy (inkl. gjeldende versjon)."""
    try:
        policy = await policy_service.get_policy(session, policy_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    current = await policy_service.get_current_version(session, policy_id)
    return _to_policy_out(policy, current)


@router.post("/{policy_id}/versions", response_model=PolicyVersionOut, status_code=status.HTTP_201_CREATED)
async def add_policy_version(
    policy_id: uuid.UUID, body: PolicyContentUpdate, session: SessionDep
) -> PolicyVersionOut:
    """Publiser ny versjon av en eksisterende policy."""
    try:
        version = await policy_service.update_policy_content(
            session,
            policy_id,
            content=body.content,
            created_by=body.created_by,
            change_summary=body.change_summary,
            law_references=[r.model_dump() for r in body.law_references] if body.law_references else None,
            effective_from=body.effective_from,
        )
        await session.commit()
        return PolicyVersionOut.model_validate(version)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{policy_id}/versions", response_model=list[PolicyVersionOut])
async def list_versions(policy_id: uuid.UUID, session: SessionDep) -> list[PolicyVersionOut]:
    """Hent komplett versjonshistorikk for en policy."""
    try:
        await policy_service.get_policy(session, policy_id)  # sjekk eksistens
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    versions = await policy_service.list_versions(session, policy_id)
    return [PolicyVersionOut.model_validate(v) for v in versions]


@router.patch("/{policy_id}", response_model=PolicyOut)
async def update_policy_metadata(
    policy_id: uuid.UUID, body: PolicyMetadataUpdate, session: SessionDep
) -> PolicyOut:
    """Oppdater metadata (tittel, kategori, eier, aktiv-status) uten ny versjon."""
    try:
        policy = await policy_service.update_policy_metadata(
            session,
            policy_id,
            title=body.title,
            category=body.category,
            owner=body.owner,
            is_active=body.is_active,
        )
        await session.commit()
        current = await policy_service.get_current_version(session, policy_id)
        return _to_policy_out(policy, current)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
