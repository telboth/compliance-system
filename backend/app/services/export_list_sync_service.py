"""Tjeneste for automatisk sjekk og import av DEKSAs varelister.

Flyten er:
  1. check_for_updates()  — HTTP HEAD mot source_url, sammenligner ETag/Last-Modified.
                            Setter status='update_available' og varsler ALLE brukere.
  2. trigger_import()     — Hvem som helst kan kalle denne. Laster ned filen,
                            parser og upsert-er i export_control_items, re-screener
                            paavirkede fakturaer, varsler alle brukere om fullfort import.

Parseren haandterer en generisk CSV/TSV-eksport med kolonner:
  list_code, category, group, item_code, title, regime, cas_numbers, synonyms, hs_codes

Dette er formatet import_export_control_list.py produserer. For EU Annex I Excel
maa en separat konverteringsjobb lage denne CSV-en forst (se scripts/).

VIKTIG: Tjenesten er beslutningsstotte. Ingen automatisk re-scoring uten
manuell godkjenning — backfill_export_control kjoeres kun naar triggered manuelt.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.export_list_sync import ExportListSyncState
from app.services import notification_service

log = logging.getLogger(__name__)

_LIST_CODES = ("I", "II")
_STATUS_IDLE = "idle"
_STATUS_CHECKING = "checking"
_STATUS_AVAILABLE = "update_available"
_STATUS_IMPORTING = "importing"
_STATUS_OK = "ok"
_STATUS_ERROR = "error"


# ── Hjelp ─────────────────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(UTC)


async def _get_or_create_state(session: AsyncSession, list_code: str) -> ExportListSyncState:
    row = (
        (await session.execute(select(ExportListSyncState).where(ExportListSyncState.list_code == list_code)))
        .scalars()
        .first()
    )
    if row is None:
        row = ExportListSyncState(list_code=list_code, status=_STATUS_IDLE)
        session.add(row)
        await session.flush()
    return row


async def get_all_states(session: AsyncSession) -> list[ExportListSyncState]:
    """Hent tilstandsrad for begge lister (brukes av API og UI)."""
    rows = list((await session.execute(select(ExportListSyncState))).scalars().all())
    existing_codes = {r.list_code for r in rows}
    for code in _LIST_CODES:
        if code not in existing_codes:
            rows.append(await _get_or_create_state(session, code))
    await session.flush()
    return rows


async def bootstrap_seed_state(
    session: AsyncSession,
    list_code: str,
    *,
    current_version: str,
    status_message: str,
    item_count: int | None = None,
    last_imported_by: str = "seed",
) -> ExportListSyncState:
    """Sett initial sync-metadata for en statisk seedet liste.

    Brukes kun når raden fortsatt er tom og ukonfigurert. En aktiv source_url
    eller eksisterende synkroniseringshistorikk skal ikke overskrives.
    """
    state = await _get_or_create_state(session, list_code)
    has_existing_sync_data = any(
        value is not None
        for value in (
            state.current_version,
            state.last_checked_at,
            state.last_imported_at,
            state.last_imported_by,
            state.item_count,
        )
    )
    if state.source_url or state.status != _STATUS_IDLE or has_existing_sync_data:
        return state

    now = _now()
    state.status = _STATUS_OK
    state.status_message = status_message
    state.current_version = current_version
    state.last_checked_at = now
    state.last_imported_at = now
    state.last_imported_by = last_imported_by
    state.item_count = item_count
    await session.flush()
    return state


# ── Sjekk for oppdateringer ───────────────────────────────────────────────────


async def check_for_updates(session: AsyncSession) -> dict[str, str]:
    """Sjekk om listekildene har ny versjon via HTTP HEAD.

    For hver liste med konfigurert source_url:
      - Sender HTTP HEAD med If-None-Match / If-Modified-Since
      - 304 = ingen endring
      - 200 med ny ETag/Last-Modified = ny versjon tilgjengelig
      - Oppdaterer status og varsler alle brukere dersom ny versjon

    Returnerer {list_code: "updated" | "unchanged" | "no_url" | "error"}.
    """
    results: dict[str, str] = {}
    for code in _LIST_CODES:
        state = await _get_or_create_state(session, code)
        if not state.source_url:
            results[code] = "no_url"
            continue

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
                results[code] = "unchanged"
            elif resp.status_code == 200:
                new_etag = resp.headers.get("etag")
                new_lm = resp.headers.get("last-modified")
                if new_etag and new_etag == state.last_etag:
                    state.status = _STATUS_OK
                    results[code] = "unchanged"
                else:
                    state.status = _STATUS_AVAILABLE
                    state.last_etag = new_etag or state.last_etag
                    state.last_modified = new_lm or state.last_modified
                    label = "Militaer vareliste" if code == "I" else "Dual-use vareliste"
                    state.status_message = f"Ny versjon tilgjengelig for {label}"
                    results[code] = "updated"
                    log.info("export_list_update_available list_code=%s", code)
                    await notification_service.create(
                        session,
                        message=(
                            f"Oppdatering tilgjengelig: {label} (Vareliste {code}) "
                            "har ny versjon. Klikk 'Importer' for aa oppdatere."
                        ),
                        level="info",
                        target_roles=["all"],
                    )
            else:
                state.status = _STATUS_ERROR
                state.status_message = f"HTTP {resp.status_code} ved sjekk av {state.source_url}"
                results[code] = "error"
                log.warning("export_list_check_failed list_code=%s status=%s", code, resp.status_code)
        except Exception as exc:
            state.status = _STATUS_ERROR
            state.status_message = f"Feil ved sjekk: {exc}"
            results[code] = "error"
            log.exception("export_list_check_exception list_code=%s", code)

    await session.commit()
    return results


# ── Import ────────────────────────────────────────────────────────────────────


def _parse_csv(content: str) -> list[dict[str, str]]:
    """Parser en CSV/TSV med varelistepunkter.

    Forventet header (tab- eller kommaseparert):
      list_code, category, group, item_code, title, regime,
      cas_numbers, synonyms, hs_codes
    """
    dialect = "excel-tab" if "\t" in content[:1024] else "excel"
    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    rows = []
    for row in reader:
        cleaned = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        if cleaned.get("item_code"):
            rows.append(cleaned)
    return rows


async def trigger_import(
    session: AsyncSession,
    list_code: str,
    *,
    triggered_by: str = "unknown",
) -> dict[str, object]:
    """Last ned og importer vareliste.

    Laster ned CSV fra source_url, upsert-er alle rader i export_control_items,
    og varsler alle brukere om resultatet.

    Returnerer {"created": int, "updated": int, "errors": int}.
    """
    from app.services.export_control_service import count_items, upsert_item

    state = await _get_or_create_state(session, list_code)
    if not state.source_url:
        raise ValueError(f"Ingen source_url konfigurert for Vareliste {list_code}")

    state.status = _STATUS_IMPORTING
    state.status_message = f"Import startet av {triggered_by}"
    await session.flush()

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(state.source_url, follow_redirects=True)
        resp.raise_for_status()

        content = resp.text
        rows = _parse_csv(content)
        if not rows:
            raise ValueError("Filen inneholder ingen gyldige rader — sjekk CSV-format")

        version = resp.headers.get("last-modified") or _now().strftime("%Y-%m-%dT%H:%M")
        source_version = f"auto-{list_code}-{version[:10]}"

        created = updated = errors = 0
        for row in rows:
            try:
                is_new = await upsert_item(
                    session,
                    list_code=row.get("list_code", list_code),
                    category=row.get("category", ""),
                    group=row.get("group") or None,
                    item_code=row.get("item_code", ""),
                    title=row.get("title") or None,
                    regime=row.get("regime") or None,
                    source_version=source_version,
                    cas_numbers=row.get("cas_numbers") or None,
                    synonyms=row.get("synonyms") or None,
                    hs_codes=row.get("hs_codes") or None,
                )
                if is_new:
                    created += 1
                else:
                    updated += 1
            except Exception:
                errors += 1
                log.exception("export_list_row_error row=%r", row)

        total = await count_items(session)
        label = "Militaer vareliste" if list_code == "I" else "Dual-use vareliste"
        state.status = _STATUS_OK
        state.status_message = f"Import fullfort: {created} nye, {updated} oppdatert, {errors} feil"
        state.last_imported_at = _now()
        state.last_imported_by = triggered_by
        state.current_version = source_version
        state.item_count = total
        state.last_etag = resp.headers.get("etag") or state.last_etag
        state.last_modified = resp.headers.get("last-modified") or state.last_modified

        await session.commit()
        log.info(
            "export_list_import_done list_code=%s created=%d updated=%d errors=%d",
            list_code,
            created,
            updated,
            errors,
        )

        await notification_service.create(
            session,
            message=(
                f"Vareliste {list_code} ({label}) er oppdatert av {triggered_by}: "
                f"{created} nye, {updated} endrede punkter. "
                "Kjor bakfylling for aa re-score eksisterende fakturaer."
            ),
            level="info",
            target_roles=["all"],
        )
        await session.commit()

        return {"created": created, "updated": updated, "errors": errors, "total": total}

    except Exception as exc:
        state.status = _STATUS_ERROR
        state.status_message = f"Import feilet: {exc}"
        await session.commit()
        log.exception("export_list_import_failed list_code=%s", list_code)
        raise


async def set_source_url(
    session: AsyncSession,
    list_code: str,
    url: str,
) -> ExportListSyncState:
    """Oppdater nedlastings-URL for en liste (kalt fra konfig-API-et)."""
    state = await _get_or_create_state(session, list_code)
    state.source_url = url
    state.status = _STATUS_IDLE
    state.status_message = "URL oppdatert — klikk Sjekk for aa verifisere"
    await session.commit()
    return state
