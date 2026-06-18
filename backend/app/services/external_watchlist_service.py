"""Daglig ingest og health for eksterne watchlist-kilder."""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.models.external_watchlist_entry import ExternalWatchlistEntry
from app.models.sanctions_list import SanctionsList

logger = get_logger(__name__)

SOURCE_UK_SANCTIONS = "uk_sanctions_external"
SOURCE_WORLD_BANK_DEBARRED = "world_bank_debarred_external"
SOURCE_BRREG_LOOKUP = "brreg_registry_lookup"

_UK_SANCTIONS_CSV_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv"
_WORLD_BANK_DEBARRED_API_URL = (
    "https://apigwext.worldbank.org/dvsvc/v1.0/json/APPLICATION/ADOBE_EXPRNCE_MGR/FIRM/SANCTIONED_FIRM"
)
_BRREG_ENHETER_API_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"

_EXTERNAL_INGEST_LOCK_KEY = 884_120_741


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", value).lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _first_non_empty(row: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


async def _get_or_create_status_row(session: AsyncSession, source: str) -> SanctionsList:
    row = (await session.execute(select(SanctionsList).where(SanctionsList.source == source))).scalar_one_or_none()
    if row:
        return row
    row = SanctionsList(source=source, update_status="unknown")
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _store_entries(
    session: AsyncSession,
    *,
    source: str,
    rows: list[dict[str, Any]],
) -> None:
    await session.execute(delete(ExternalWatchlistEntry).where(ExternalWatchlistEntry.source == source))
    if rows:
        await session.execute(insert(ExternalWatchlistEntry), rows)


def _parse_uk_sanctions_csv(text_payload: str) -> list[dict[str, Any]]:
    lines = text_payload.splitlines()
    if len(lines) < 2:
        return []

    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])))
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    now = datetime.now(UTC)

    for row in reader:
        if not isinstance(row, dict):
            continue
        external_id = str(row.get("Unique ID") or "").strip()
        name = _first_non_empty(row, ["Name 6", "Name 1", "Name 2", "Name 3", "Name 4", "Name 5"])
        if not name:
            continue
        key = (external_id, name.lower())
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "source": SOURCE_UK_SANCTIONS,
                "external_id": external_id or None,
                "name": name[:512],
                "name_normalized": normalize_name(name)[:512],
                "country": (str(row.get("Country") or "").strip() or None),
                "sanctions_type": (str(row.get("Sanctions Imposed") or "").strip() or None),
                "listed_from": (str(row.get("Date Designated") or "").strip() or None),
                "listed_to": (str(row.get("Date sanctions effective until") or "").strip() or None),
                "notes": (str(row.get("Other Information") or "").strip() or None),
                "raw_payload": row,
                "updated_at": now,
            }
        )
    return out


def _parse_world_bank_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw_rows = ((payload or {}).get("response") or {}).get("ZPROCSUPP") or []
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    now = datetime.now(UTC)

    for row in raw_rows:
        if not isinstance(row, dict):
            continue
        external_id = str(row.get("SUPP_ID") or "").strip()
        name = str(row.get("SUPP_NAME") or "").strip()
        if not name:
            continue
        key = (external_id, name.lower())
        if key in seen:
            continue
        seen.add(key)

        out.append(
            {
                "source": SOURCE_WORLD_BANK_DEBARRED,
                "external_id": external_id or None,
                "name": name[:512],
                "name_normalized": normalize_name(name)[:512],
                "country": (str(row.get("COUNTRY_NAME") or "").strip() or None),
                "sanctions_type": (str(row.get("DEBAR_TYPE") or "").strip() or None),
                "listed_from": (str(row.get("DEBAR_FROM_DATE") or "").strip() or None),
                "listed_to": (str(row.get("DEBAR_TO_DATE") or "").strip() or None),
                "notes": (str(row.get("DEBAR_REASON") or "").strip() or None),
                "raw_payload": row,
                "updated_at": now,
            }
        )

    return out


async def ingest_external_watchlists(session: AsyncSession) -> list[dict[str, Any]]:
    settings = get_settings()
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(
        timeout=90.0,
        follow_redirects=True,
        headers={"User-Agent": "xlent-compliance-mvp/0.1 (external-watchlist-ingest)"},
    ) as client:
        uk_status = await _get_or_create_status_row(session, SOURCE_UK_SANCTIONS)
        uk_status.update_status = "updating"
        uk_status.error_message = None
        await session.commit()
        try:
            uk_resp = await client.get(_UK_SANCTIONS_CSV_URL)
            uk_resp.raise_for_status()
            uk_rows = _parse_uk_sanctions_csv(uk_resp.text)
            await _store_entries(session, source=SOURCE_UK_SANCTIONS, rows=uk_rows)
            uk_status.update_status = "success"
            uk_status.last_updated = datetime.now(UTC)
            uk_status.entry_count = len(uk_rows)
            uk_status.error_message = None
            await session.commit()
            results.append(
                {
                    "source": SOURCE_UK_SANCTIONS,
                    "status": "success",
                    "entry_count": len(uk_rows),
                }
            )
        except Exception as exc:
            uk_status.update_status = "failed"
            uk_status.error_message = str(exc)[:1000]
            await session.commit()
            results.append({"source": SOURCE_UK_SANCTIONS, "status": "failed", "entry_count": 0})
            logger.exception("external_watchlist_ingest_failed", source=SOURCE_UK_SANCTIONS)

        wb_status = await _get_or_create_status_row(session, SOURCE_WORLD_BANK_DEBARRED)
        wb_status.update_status = "updating"
        wb_status.error_message = None
        await session.commit()
        try:
            wb_resp = await client.get(
                _WORLD_BANK_DEBARRED_API_URL,
                headers={"apikey": settings.world_bank_debarred_api_key},
            )
            wb_resp.raise_for_status()
            wb_rows = _parse_world_bank_payload(wb_resp.json())
            await _store_entries(session, source=SOURCE_WORLD_BANK_DEBARRED, rows=wb_rows)
            wb_status.update_status = "success"
            wb_status.last_updated = datetime.now(UTC)
            wb_status.entry_count = len(wb_rows)
            wb_status.error_message = None
            await session.commit()
            results.append(
                {
                    "source": SOURCE_WORLD_BANK_DEBARRED,
                    "status": "success",
                    "entry_count": len(wb_rows),
                }
            )
        except Exception as exc:
            wb_status.update_status = "failed"
            wb_status.error_message = str(exc)[:1000]
            await session.commit()
            results.append(
                {
                    "source": SOURCE_WORLD_BANK_DEBARRED,
                    "status": "failed",
                    "entry_count": 0,
                }
            )
            logger.exception("external_watchlist_ingest_failed", source=SOURCE_WORLD_BANK_DEBARRED)

    return results


async def run_external_watchlist_ingest_cycle() -> dict[str, Any]:
    async with get_session_factory()() as session:
        locked = await _try_acquire_lock(session)
        if not locked:
            logger.warning("external_watchlist_ingest_skipped_lock_busy")
            return {"started": False, "message": "Ekstern kilde-ingest er allerede i gang."}
        try:
            rows = await ingest_external_watchlists(session)
            return {"started": True, "message": "Eksterne kilder oppdatert.", "sources": rows}
        finally:
            await _release_lock(session)


async def list_external_source_health(
    session: AsyncSession,
    *,
    include_brreg_probe: bool = True,
) -> list[dict[str, Any]]:
    settings = get_settings()
    stale_after = timedelta(hours=max(1, settings.external_source_stale_hours))
    rows = (
        (
            await session.execute(
                select(SanctionsList).where(SanctionsList.source.in_([SOURCE_UK_SANCTIONS, SOURCE_WORLD_BANK_DEBARRED]))
            )
        )
        .scalars()
        .all()
    )
    by_source = {row.source: row for row in rows}

    out: list[dict[str, Any]] = []
    for source in (SOURCE_UK_SANCTIONS, SOURCE_WORLD_BANK_DEBARRED):
        row = by_source.get(source)
        stale = False
        if row and row.last_updated:
            stale = datetime.now(UTC) - row.last_updated > stale_after
        out.append(
            {
                "source": source,
                "enabled": True,
                "status": row.update_status if row else "unknown",
                "entry_count": row.entry_count if row else None,
                "last_updated": row.last_updated if row else None,
                "error_message": row.error_message if row else None,
                "stale": stale,
            }
        )

    brreg_status = "unknown"
    brreg_error = None
    if include_brreg_probe:
        brreg_status = "ok"
        try:
            async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
                resp = await client.get(
                    _BRREG_ENHETER_API_URL,
                    params={"navn": "Equinor", "size": 1},
                )
                resp.raise_for_status()
        except Exception as exc:
            brreg_status = "failed"
            brreg_error = str(exc)[:500]

    out.append(
        {
            "source": SOURCE_BRREG_LOOKUP,
            "enabled": True,
            "status": brreg_status,
            "entry_count": None,
            "last_updated": None,
            "error_message": brreg_error,
            "stale": False,
        }
    )
    return out


async def _try_acquire_lock(session: AsyncSession) -> bool:
    result = await session.execute(
        text("SELECT pg_try_advisory_lock(:key)"),
        {"key": _EXTERNAL_INGEST_LOCK_KEY},
    )
    return bool(result.scalar_one())


async def _release_lock(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT pg_advisory_unlock(:key)"),
        {"key": _EXTERNAL_INGEST_LOCK_KEY},
    )
