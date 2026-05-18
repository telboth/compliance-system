"""Orkestrering av sanksjonsoppdatering med overlapp-beskyttelse."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import desc, select, text

from app.core.config import get_settings
from app.core.database import AsyncSession, get_session_factory
from app.core.logging import get_logger
from app.models.sanctions_refresh_run import SanctionsRefreshRun
from app.sanctions.yente_client import get_yente_client
from app.services.sanctions_loader_service import refresh_local_sanctions_sources

logger = get_logger(__name__)

# Stabil advisory lock-id for sanksjonsrefresh.
# Må være samme verdi i alle prosesser/containere.
_SANCTIONS_REFRESH_LOCK_KEY = 884_120_740


@dataclass(frozen=True)
class SanctionsRefreshResult:
    started: bool
    message: str


async def run_sanctions_refresh_cycle() -> SanctionsRefreshResult:
    """Kjør en hel refresh-syklus hvis ingen annen refresh allerede kjører."""
    return await run_sanctions_refresh_cycle_with_trigger(trigger="manual")


async def run_sanctions_refresh_cycle_with_trigger(
    *,
    trigger: str,
) -> SanctionsRefreshResult:
    """Kjør en hel refresh-syklus med eksplisitt trigger-kilde."""
    async with get_session_factory()() as session:
        started_at = datetime.now(UTC)

        locked = await _try_acquire_refresh_lock(session)
        if not locked:
            await _create_refresh_run(
                session=session,
                trigger=trigger,
                status="skipped",
                message="Sanksjonsoppdatering er allerede i gang.",
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
            logger.warning("sanctions_refresh_skipped_lock_busy")
            return SanctionsRefreshResult(
                started=False,
                message="Sanksjonsoppdatering er allerede i gang.",
            )

        run_row = await _create_refresh_run(
            session=session,
            trigger=trigger,
            status="running",
            message="Sanksjonsoppdatering startet.",
            started_at=started_at,
            finished_at=None,
        )
        try:
            await refresh_local_sanctions_sources(session)

            settings = get_settings()
            token = settings.yente_update_token.strip()
            if not token:
                raise RuntimeError("Mangler YENTE_UPDATE_TOKEN for kall til /updatez.")

            yente = get_yente_client()
            response = await yente.trigger_update(token=token, sync=False)
            if response.status_code in {401, 403}:
                raise RuntimeError(
                    "Yente avviste /updatez-token "
                    f"(HTTP {response.status_code})."
                )
            response.raise_for_status()

            run_row.status = "success"
            run_row.message = "Sanksjonsoppdatering trigget."
            run_row.finished_at = datetime.now(UTC)
            await session.commit()

            logger.info("sanctions_refresh_cycle_completed")
            return SanctionsRefreshResult(
                started=True,
                message="Sanksjonsoppdatering trigget.",
            )
        except Exception as exc:
            run_row.status = "failed"
            run_row.message = str(exc)[:1000]
            run_row.finished_at = datetime.now(UTC)
            await session.commit()
            raise
        finally:
            await _release_refresh_lock(session)


async def _try_acquire_refresh_lock(session: AsyncSession) -> bool:
    result = await session.execute(
        text("SELECT pg_try_advisory_lock(:key)"),
        {"key": _SANCTIONS_REFRESH_LOCK_KEY},
    )
    return bool(result.scalar_one())


async def _release_refresh_lock(session: AsyncSession) -> None:
    try:
        await session.execute(
            text("SELECT pg_advisory_unlock(:key)"),
            {"key": _SANCTIONS_REFRESH_LOCK_KEY},
        )
    except Exception:
        logger.exception("sanctions_refresh_unlock_failed")


async def _create_refresh_run(
    *,
    session: AsyncSession,
    trigger: str,
    status: str,
    message: str,
    started_at: datetime,
    finished_at: datetime | None,
) -> SanctionsRefreshRun:
    row = SanctionsRefreshRun(
        trigger=trigger,
        status=status,
        message=message,
        started_at=started_at,
        finished_at=finished_at,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_latest_refresh_run(session: AsyncSession) -> SanctionsRefreshRun | None:
    """Hent nyeste refresh-forsok for operasjonell statusvisning."""
    result = await session.execute(
        select(SanctionsRefreshRun).order_by(desc(SanctionsRefreshRun.started_at)).limit(1)
    )
    return result.scalar_one_or_none()
