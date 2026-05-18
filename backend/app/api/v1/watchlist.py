"""Intern sperreliste-API — CRUD for watchlist-oppføringer."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.core.database import SessionDep
from app.core.errors import NotFoundError
from app.services import internal_watchlist_service as wl_svc

router = APIRouter()


# ── Pydantic-skjemaer ──────────────────────────────────────────────────────────


class WatchlistEntryOut(BaseModel):
    id: uuid.UUID
    entry_type: str
    value: str
    reason: str | None
    severity: str
    added_by: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WatchlistListResponse(BaseModel):
    total: int
    items: list[WatchlistEntryOut]


class WatchlistEntryCreate(BaseModel):
    entry_type: str          # "name" | "email_domain" | "country" | "regex"
    value: str
    reason: str | None = None
    severity: str = "red"    # "yellow" | "red"
    added_by: str = "admin"


class WatchlistEntryUpdate(BaseModel):
    value: str | None = None
    reason: str | None = None
    severity: str | None = None
    is_active: bool | None = None


# ── Endepunkter ────────────────────────────────────────────────────────────────


@router.get("", response_model=WatchlistListResponse)
async def list_watchlist(
    session: SessionDep,
    active_only: bool = Query(default=True, description="Vis kun aktive oppføringer"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> WatchlistListResponse:
    """List alle oppføringer i den interne sperrelisten."""
    entries, total = await wl_svc.list_entries(
        session, active_only=active_only, limit=limit, offset=offset
    )
    return WatchlistListResponse(
        total=total,
        items=[WatchlistEntryOut.model_validate(e) for e in entries],
    )


@router.post("", response_model=WatchlistEntryOut, status_code=status.HTTP_201_CREATED)
async def create_watchlist_entry(
    body: WatchlistEntryCreate,
    session: SessionDep,
) -> WatchlistEntryOut:
    """Legg til en ny oppføring i sperrelisten."""
    try:
        entry = await wl_svc.create_entry(
            session,
            entry_type=body.entry_type,
            value=body.value,
            reason=body.reason,
            severity=body.severity,
            added_by=body.added_by,
        )
        await session.commit()
        await session.refresh(entry)
        return WatchlistEntryOut.model_validate(entry)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{entry_id}", response_model=WatchlistEntryOut)
async def get_watchlist_entry(
    entry_id: uuid.UUID,
    session: SessionDep,
) -> WatchlistEntryOut:
    try:
        entry = await wl_svc.get_entry(session, entry_id)
        return WatchlistEntryOut.model_validate(entry)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{entry_id}", response_model=WatchlistEntryOut)
async def update_watchlist_entry(
    entry_id: uuid.UUID,
    body: WatchlistEntryUpdate,
    session: SessionDep,
) -> WatchlistEntryOut:
    """Oppdater en watchlist-oppføring (f.eks. deaktiver eller endre verdi)."""
    try:
        entry = await wl_svc.update_entry(
            session,
            entry_id,
            value=body.value,
            reason=body.reason,
            severity=body.severity,
            is_active=body.is_active,
        )
        await session.commit()
        await session.refresh(entry)
        return WatchlistEntryOut.model_validate(entry)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_watchlist_entry(
    entry_id: uuid.UUID,
    session: SessionDep,
) -> Response:
    """Slett en watchlist-oppføring permanent."""
    try:
        await wl_svc.delete_entry(session, entry_id)
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{entry_id}/toggle", response_model=WatchlistEntryOut)
async def toggle_watchlist_entry(
    entry_id: uuid.UUID,
    session: SessionDep,
) -> WatchlistEntryOut:
    """Skru av/på en watchlist-oppføring."""
    try:
        entry = await wl_svc.get_entry(session, entry_id)
        entry.is_active = not entry.is_active
        await session.commit()
        await session.refresh(entry)
        return WatchlistEntryOut.model_validate(entry)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
