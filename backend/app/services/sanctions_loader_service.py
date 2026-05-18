"""Lokal nedlasting/parsing av sanksjonslister."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.sanctions_list import SanctionsList
from app.sanctions.loaders.eu import parse_eu_count
from app.sanctions.loaders.ofac import parse_ofac_count
from app.sanctions.loaders.un import parse_un_count

logger = get_logger(__name__)


@dataclass(frozen=True)
class SanctionsSource:
    source: str
    urls: tuple[str, ...]
    parser: Callable[[bytes], int]
    filename: str


_SOURCES: tuple[SanctionsSource, ...] = (
    SanctionsSource(
        source="un_sc_sanctions",
        urls=("https://scsanctions.un.org/resources/xml/en/consolidated.xml",),
        parser=parse_un_count,
        filename="un_sc_sanctions.xml",
    ),
    SanctionsSource(
        source="eu_fsf",
        urls=(
            # Primarkilde fra DG FISMA.
            "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content",
            # Fallback: offentlig speilet kopi (Latvia FIU) for robusthet ved 403/rate-limit.
            "https://sankcijas.fid.gov.lv/files/xmlFullSanctionsList_1_1.xml",
        ),
        parser=parse_eu_count,
        filename="eu_fsf.xml",
    ),
    SanctionsSource(
        source="us_ofac_sdn",
        urls=("https://www.treasury.gov/ofac/downloads/sdn.csv",),
        parser=parse_ofac_count,
        filename="us_ofac_sdn.csv",
    ),
    SanctionsSource(
        source="us_ofac_cons",
        urls=("https://www.treasury.gov/ofac/downloads/consolidated/cons_prim.csv",),
        parser=parse_ofac_count,
        filename="us_ofac_cons.csv",
    ),
)


async def refresh_local_sanctions_sources(session: AsyncSession) -> list[dict[str, str | int]]:
    """Last ned og parse alle gratis kilder, oppdater status i DB."""
    settings = get_settings()
    cache_dir = Path(settings.upload_dir) / "sanctions_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, str | int]] = []
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        for source in _SOURCES:
            now = datetime.now(UTC)
            status_row = await _get_or_create_status_row(session, source.source)
            status_row.update_status = "updating"
            status_row.error_message = None
            await session.commit()

            try:
                payload, selected_url = await _download_with_fallback(
                    client=client,
                    source=source,
                )
                entry_count = int(source.parser(payload))
                local_path = cache_dir / source.filename
                local_path.write_bytes(payload)

                status_row.entry_count = entry_count
                status_row.last_updated = now
                status_row.update_status = "success"
                status_row.error_message = None
                await session.commit()
                results.append(
                    {
                        "source": source.source,
                        "status": "success",
                        "entry_count": entry_count,
                    }
                )
                logger.info(
                    "sanctions_source_refreshed",
                    source=source.source,
                    entry_count=entry_count,
                    url=selected_url,
                    path=str(local_path),
                )
            except Exception as exc:
                status_row.update_status = "failed"
                status_row.error_message = str(exc)[:1000]
                await session.commit()
                results.append(
                    {
                        "source": source.source,
                        "status": "failed",
                        "entry_count": 0,
                    }
                )
                logger.exception(
                    "sanctions_source_refresh_failed",
                    source=source.source,
                )

    return results


async def list_local_sanctions_statuses(session: AsyncSession) -> list[SanctionsList]:
    """Returner lokale statusrader for alle kilder."""
    result = await session.execute(
        select(SanctionsList).order_by(SanctionsList.source.asc())
    )
    return list(result.scalars().all())


async def _get_or_create_status_row(session: AsyncSession, source: str) -> SanctionsList:
    row = (
        await session.execute(select(SanctionsList).where(SanctionsList.source == source))
    ).scalar_one_or_none()
    if row:
        return row
    row = SanctionsList(source=source, update_status="unknown")
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def _download_with_fallback(
    *,
    client: httpx.AsyncClient,
    source: SanctionsSource,
) -> tuple[bytes, str]:
    """Last ned en kilde med URL-fallback og diagnostikk."""
    errors: list[str] = []
    for url in source.urls:
        try:
            response = await client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": "*/*",
                    "Referer": "https://finance.ec.europa.eu/",
                },
            )
            response.raise_for_status()
            payload = response.content
            if not payload:
                raise ValueError("Empty payload")
            return payload, url
        except Exception as exc:
            errors.append(f"{url} -> {exc}")

    raise RuntimeError("; ".join(errors))
