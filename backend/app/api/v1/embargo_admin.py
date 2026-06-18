"""Embargo-administrasjon API.

Endepunkter:
  GET  /embargo/countries        — liste alle aktive embargoland
  GET  /embargo/sync/status      — synkroniseringsstatus
  POST /embargo/sync/check       — sjekk for ny versjon (alle brukere)
  POST /embargo/sync/import      — importer lista (alle brukere)
  PUT  /embargo/sync/url         — sett nedlastings-URL (admin)
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.core.database import SessionDep
from app.core.security import ActorContext, require_roles
from app.services import embargo_sync_service as sync_svc

router = APIRouter()


class EmbargoCountryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    iso2: str
    name: str
    sources: str
    scope: str
    note: str | None
    source_version: str


class EmbargoSyncStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    list_code: str
    source_url: str | None
    current_version: str | None
    status: str
    status_message: str | None
    last_checked_at: datetime | None
    last_imported_at: datetime | None
    last_imported_by: str | None
    item_count: int | None


class EmbargoImportOut(BaseModel):
    created: int
    updated: int
    deactivated: int
    total: int


@router.get("/countries", response_model=list[EmbargoCountryOut])
async def list_embargo_countries(session: SessionDep) -> list[EmbargoCountryOut]:
    """Hent alle aktive embargoland fra DB (alle brukere)."""
    rows = await sync_svc.list_countries(session)
    return [EmbargoCountryOut.model_validate(r) for r in rows]


@router.get("/sync/status", response_model=EmbargoSyncStateOut)
async def get_sync_status(session: SessionDep) -> EmbargoSyncStateOut:
    """Hent synkroniseringsstatus for embargo-lista (alle brukere)."""
    state = await sync_svc.get_state(session)
    await session.commit()
    return EmbargoSyncStateOut.model_validate(state)


@router.post("/sync/check", response_model=dict[str, object])
async def check_for_updates(session: SessionDep) -> dict[str, object]:
    """Sjekk manuelt om embargo-lista har ny versjon (alle brukere)."""
    result = await sync_svc.check_for_updates(session)
    return {"status": "ok", "result": result}


@router.post("/sync/import", response_model=EmbargoImportOut)
async def import_embargo_list(
    session: SessionDep,
    actor: str = Query(default="unknown", description="Brukerident for sporing"),
) -> EmbargoImportOut:
    """Last ned og importer embargo-lista (alle brukere kan trigge).

    Varsler alle brukere nar importen er fullfort og reloader in-memory cachen
    slik at alle nye screeninger bruker den oppdaterte listen umiddelbart.
    """
    try:
        result = await sync_svc.trigger_import(session, triggered_by=actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return EmbargoImportOut(**result)


@router.put("/sync/url")
async def set_source_url(
    session: SessionDep,
    url: str = Query(..., description="Nedlastings-URL for embargo-CSV"),
    _actor: ActorContext = Depends(require_roles("admin")),
) -> EmbargoSyncStateOut:
    """Oppdater nedlastings-URL for embargo-lista (kun admin).

    CSV-format (tab eller komma):
      iso2, name, sources, scope, note
    """
    state = await sync_svc.set_source_url(session, url)
    return EmbargoSyncStateOut.model_validate(state)
