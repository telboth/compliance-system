"""Tjeneste for automatisk sjekk og import av embargo-/sanksjonslanden.

Gjenbruker ExportListSyncState med list_code='embargo' for aa spore
URL, ETag og importhistorikk. Samme flyt som export_list_sync_service:

  1. check_for_updates() — HTTP HEAD, varsler alle brukere ved ny versjon.
  2. trigger_import()    — Last ned CSV, upsert EmbargoCountry, reload cache,
                          varsler alle brukere om fullfort import.

CSV-format (tab eller komma):
  iso2, name, sources, scope, note
  KP,"Nord-Korea (DPRK)","UN,EU,NO,US",comprehensive,"FN SR res. ..."
  RU,Russland,"EU,NO",sectoral,"EU-forordning 833/2014..."

En seed-CSV basert paa gjeldende statisk liste leveres i scripts/.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.embargo_country import EmbargoCountry
from app.models.export_list_sync import ExportListSyncState
from app.services import notification_service

log = logging.getLogger(__name__)

_LIST_CODE = "embargo"
_STATUS_IDLE = "idle"
_STATUS_CHECKING = "checking"
_STATUS_AVAILABLE = "update_available"
_STATUS_IMPORTING = "importing"
_STATUS_OK = "ok"
_STATUS_ERROR = "error"


def _now() -> datetime:
    return datetime.now(UTC)


async def _get_state(session: AsyncSession) -> ExportListSyncState:
    row = (
        await session.execute(
            select(ExportListSyncState).where(ExportListSyncState.list_code == _LIST_CODE)
        )
    ).scalars().first()
    if row is None:
        row = ExportListSyncState(list_code=_LIST_CODE, status=_STATUS_IDLE)
        session.add(row)
        await session.flush()
    return row


async def get_state(session: AsyncSession) -> ExportListSyncState:
    """Hent synkroniseringsstatus for embargo-lista (brukes av API og UI)."""
    state = await _get_state(session)
    await session.flush()
    return state


async def check_for_updates(session: AsyncSession) -> str:
    """Sjekk om embargo-lista har ny versjon via HTTP HEAD.

    Returnerer 'updated' | 'unchanged' | 'no_url' | 'error'.
    """
    state = await _get_state(session)
    if not state.source_url:
        return "no_url"

    state.status = _STATUS_CHECKING
    state.last_checked_at = _now()
    await session.flush()

    try:
        headers: dict[str, str] = {}
        if state.last_etag:
            headers["If-None-Match"] = state.last_etag
        elif state.last_modified:
            headers["If-Modified-Since"] = state.last_modified

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.head(state.source_url, headers=headers, follow_redirects=True)

        if resp.status_code == 304:
            state.status = _STATUS_OK
            state.status_message = f"Ingen endring siden {state.last_imported_at}"
            await session.commit()
            return "unchanged"

        if resp.status_code == 200:
            new_etag = resp.headers.get("etag")
            if new_etag and new_etag == state.last_etag:
                state.status = _STATUS_OK
                await session.commit()
                return "unchanged"

            state.status = _STATUS_AVAILABLE
            state.last_etag = new_etag or state.last_etag
            state.last_modified = resp.headers.get("last-modified") or state.last_modified
            state.status_message = "Ny versjon av embargo-/sanksjonslisten er tilgjengelig"
            await session.flush()
            log.info("embargo_list_update_available")
            await notification_service.create(
                session,
                message=(
                    "Oppdatering tilgjengelig: Embargo-/sanksjonslisten har ny versjon. "
                    "Klikk 'Importer' under Embargo-administrasjon for aa oppdatere."
                ),
                level="info",
                target_roles=["all"],
            )
            await session.commit()
            return "updated"

        state.status = _STATUS_ERROR
        state.status_message = f"HTTP {resp.status_code} ved sjekk av {state.source_url}"
        await session.commit()
        log.warning("embargo_list_check_failed status=%s", resp.status_code)
        return "error"

    except Exception as exc:
        state.status = _STATUS_ERROR
        state.status_message = f"Feil ved sjekk: {exc}"
        await session.commit()
        log.exception("embargo_list_check_exception")
        return "error"


def _parse_csv(content: str) -> list[dict[str, str]]:
    dialect = "excel-tab" if "\t" in content[:512] else "excel"
    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    rows = []
    for row in reader:
        cleaned = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        if cleaned.get("iso2"):
            rows.append(cleaned)
    return rows


async def trigger_import(
    session: AsyncSession,
    *,
    triggered_by: str = "unknown",
) -> dict[str, object]:
    """Last ned og importer embargo-lista.

    Upsert-er alle rader i embargo_countries, setter inaktive rader
    som er fjernet fra den nye lista, og reloader in-memory cachen.

    Returnerer {"created": int, "updated": int, "deactivated": int, "total": int}.
    """
    from app.sanctions.embargo import load_cache_from_db

    state = await _get_state(session)
    if not state.source_url:
        raise ValueError("Ingen source_url konfigurert for embargo-lista")

    state.status = _STATUS_IMPORTING
    state.status_message = f"Import startet av {triggered_by}"
    await session.flush()

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(state.source_url, follow_redirects=True)
        resp.raise_for_status()

        rows = _parse_csv(resp.text)
        if not rows:
            raise ValueError("Filen inneholder ingen gyldige rader — sjekk CSV-format")

        version = resp.headers.get("last-modified") or _now().strftime("%Y-%m-%dT%H:%M")
        source_version = f"auto-embargo-{version[:10]}"

        # Alle ISO2-koder i den nye filen
        new_iso2s: set[str] = set()
        created = updated = 0

        for row in rows:
            iso2 = row.get("iso2", "").upper().strip()
            if not iso2 or len(iso2) != 2:
                continue
            new_iso2s.add(iso2)

            existing = (
                await session.execute(
                    select(EmbargoCountry).where(EmbargoCountry.iso2 == iso2)
                )
            ).scalars().first()

            name = row.get("name", iso2)
            sources = row.get("sources", "")
            scope = row.get("scope", "sectoral")
            note = row.get("note") or None

            if existing is not None:
                existing.name = name
                existing.sources = sources
                existing.scope = scope
                existing.note = note
                existing.is_active = True
                existing.source_version = source_version
                updated += 1
            else:
                session.add(EmbargoCountry(
                    iso2=iso2,
                    name=name,
                    sources=sources,
                    scope=scope,
                    note=note,
                    is_active=True,
                    source_version=source_version,
                ))
                created += 1

        # Deaktiver land som ikke lenger er paa lista
        all_existing = list(
            (await session.execute(select(EmbargoCountry))).scalars().all()
        )
        deactivated = 0
        for row_db in all_existing:
            if row_db.iso2 not in new_iso2s and row_db.is_active:
                row_db.is_active = False
                deactivated += 1

        total = len(new_iso2s)
        state.status = _STATUS_OK
        state.status_message = (
            f"Import fullfort: {created} nye, {updated} oppdatert, {deactivated} deaktivert"
        )
        state.last_imported_at = _now()
        state.last_imported_by = triggered_by
        state.current_version = source_version
        state.item_count = total
        state.last_etag = resp.headers.get("etag") or state.last_etag
        state.last_modified = resp.headers.get("last-modified") or state.last_modified
        await session.commit()

        # Reload in-memory cache slik at alle nye screeninger bruker ny lista
        reloaded = await load_cache_from_db(session)
        log.info(
            "embargo_import_done created=%d updated=%d deactivated=%d cache=%d",
            created, updated, deactivated, reloaded,
        )

        await notification_service.create(
            session,
            message=(
                f"Embargo-/sanksjonslisten er oppdatert av {triggered_by}: "
                f"{created} nye land, {updated} endret, {deactivated} deaktivert. "
                "Alle nye screeninger bruker den oppdaterte listen."
            ),
            level="info",
            target_roles=["all"],
        )
        await session.commit()

        return {"created": created, "updated": updated, "deactivated": deactivated, "total": total}

    except Exception as exc:
        state.status = _STATUS_ERROR
        state.status_message = f"Import feilet: {exc}"
        await session.commit()
        log.exception("embargo_import_failed")
        raise


async def set_source_url(
    session: AsyncSession,
    url: str,
) -> ExportListSyncState:
    """Oppdater nedlastings-URL for embargo-lista (kun admin)."""
    state = await _get_state(session)
    state.source_url = url
    state.status = _STATUS_IDLE
    state.status_message = "URL oppdatert — klikk Sjekk for aa verifisere"
    await session.commit()
    return state


async def list_countries(session: AsyncSession) -> list[EmbargoCountry]:
    """Hent alle aktive embargoland (brukes av referanse-UI)."""
    return list(
        (
            await session.execute(
                select(EmbargoCountry)
                .where(EmbargoCountry.is_active.is_(True))
                .order_by(EmbargoCountry.scope.desc(), EmbargoCountry.iso2.asc())
            )
        )
        .scalars()
        .all()
    )
