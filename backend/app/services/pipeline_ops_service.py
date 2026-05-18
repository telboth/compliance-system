"""Operasjonelle metrikker og recovery-hjelpere for pipeline."""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_pipeline_event import InvoicePipelineEvent
from app.schemas.screening import (
    PipelineLatencySummary,
    PipelineMetricsResponse,
    PipelineRecoveryItem,
    PipelineRecoveryResponse,
    PipelineStageSummary,
)


@dataclass(frozen=True)
class _StageDefinition:
    name: str
    in_progress_status: InvoiceStatus
    failed_status: InvoiceStatus
    completion_statuses: tuple[InvoiceStatus, ...]
    stale_minutes: int


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    if p <= 0:
        return float(min(values))
    if p >= 1:
        return float(max(values))
    ordered = sorted(values)
    idx = (len(ordered) - 1) * p
    lower = int(idx)
    upper = min(lower + 1, len(ordered) - 1)
    weight = idx - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def _latency_summary(metric: str, values: list[float]) -> PipelineLatencySummary:
    if not values:
        return PipelineLatencySummary(metric=metric)
    avg = sum(values) / len(values)
    return PipelineLatencySummary(
        metric=metric,
        p50_seconds=_percentile(values, 0.5),
        p95_seconds=_percentile(values, 0.95),
        average_seconds=float(avg),
    )


def _pair_stage_durations(
    stage_events: list[InvoicePipelineEvent],
    *,
    success_action: str = "completed",
) -> list[tuple[datetime, float]]:
    """Par start->completed innen samme invoice/stage og returner sluttid + sekunder."""
    by_invoice: dict[uuid.UUID, list[InvoicePipelineEvent]] = defaultdict(list)
    for row in stage_events:
        by_invoice[row.invoice_id].append(row)

    durations: list[tuple[datetime, float]] = []
    for rows in by_invoice.values():
        rows.sort(key=lambda r: r.created_at)
        open_starts: list[datetime] = []
        for row in rows:
            if row.action == "started":
                open_starts.append(row.created_at)
                continue
            if row.action == success_action and open_starts:
                start = open_starts.pop()
                end = row.created_at
                start_ts = start if start.tzinfo else start.replace(tzinfo=UTC)
                end_ts = end if end.tzinfo else end.replace(tzinfo=UTC)
                seconds = (end_ts - start_ts).total_seconds()
                if seconds >= 0:
                    durations.append((end_ts, float(seconds)))
    return durations


def _pair_end_to_end_durations(
    rows: list[InvoicePipelineEvent],
) -> list[tuple[datetime, float]]:
    """Par parsing-start til screening-completed innen samme invoice."""
    by_invoice: dict[uuid.UUID, list[InvoicePipelineEvent]] = defaultdict(list)
    for row in rows:
        by_invoice[row.invoice_id].append(row)

    durations: list[tuple[datetime, float]] = []
    for items in by_invoice.values():
        items.sort(key=lambda r: r.created_at)
        parse_starts: list[datetime] = []
        for row in items:
            if row.stage == "parsing" and row.action == "started":
                parse_starts.append(row.created_at)
                continue
            if row.stage == "screening" and row.action == "completed" and parse_starts:
                start = parse_starts.pop()
                end = row.created_at
                start_ts = start if start.tzinfo else start.replace(tzinfo=UTC)
                end_ts = end if end.tzinfo else end.replace(tzinfo=UTC)
                seconds = (end_ts - start_ts).total_seconds()
                if seconds >= 0:
                    durations.append((end_ts, float(seconds)))
    return durations


def _minutes_since(now: datetime, value: datetime) -> int:
    ts = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return max(0, int((now - ts).total_seconds() // 60))


def _stale_thresholds() -> dict[str, int]:
    settings = get_settings()
    parsing = max(3, int((settings.parsing_timeout_seconds or 180) / 60) + 2)
    extracting = max(3, int((settings.extraction_timeout_seconds or 180) / 60) + 2)
    screening = max(
        3,
        int((settings.screening_task_soft_timeout_seconds or 120) / 60) + 2,
        int(settings.screening_watchdog_stale_minutes or 3),
    )
    return {
        "parsing": parsing,
        "extracting": extracting,
        "screening": screening,
    }


def _stage_definitions() -> list[_StageDefinition]:
    stale = _stale_thresholds()
    return [
        _StageDefinition(
            name="parsing",
            in_progress_status=InvoiceStatus.PARSING,
            failed_status=InvoiceStatus.PARSING_FAILED,
            completion_statuses=(
                InvoiceStatus.PARSED,
                InvoiceStatus.EXTRACTING,
                InvoiceStatus.EXTRACTED,
                InvoiceStatus.SCREENING,
                InvoiceStatus.SCREENED,
                InvoiceStatus.SCREENING_FAILED,
                InvoiceStatus.REVIEWED,
                InvoiceStatus.APPROVED,
                InvoiceStatus.BLOCKED,
            ),
            stale_minutes=stale["parsing"],
        ),
        _StageDefinition(
            name="extracting",
            in_progress_status=InvoiceStatus.EXTRACTING,
            failed_status=InvoiceStatus.EXTRACTION_FAILED,
            completion_statuses=(
                InvoiceStatus.EXTRACTED,
                InvoiceStatus.SCREENING,
                InvoiceStatus.SCREENED,
                InvoiceStatus.SCREENING_FAILED,
                InvoiceStatus.REVIEWED,
                InvoiceStatus.APPROVED,
                InvoiceStatus.BLOCKED,
            ),
            stale_minutes=stale["extracting"],
        ),
        _StageDefinition(
            name="screening",
            in_progress_status=InvoiceStatus.SCREENING,
            failed_status=InvoiceStatus.SCREENING_FAILED,
            completion_statuses=(
                InvoiceStatus.SCREENED,
                InvoiceStatus.REVIEWED,
                InvoiceStatus.APPROVED,
                InvoiceStatus.BLOCKED,
            ),
            stale_minutes=stale["screening"],
        ),
    ]


async def get_pipeline_metrics(
    session: AsyncSession,
    *,
    lookback_hours: int = 24,
) -> PipelineMetricsResponse:
    now = datetime.now(UTC)
    lookback = max(1, min(24 * 14, int(lookback_hours or 24)))
    since = now - timedelta(hours=lookback)

    total_invoices = int(
        (await session.execute(select(func.count()).select_from(Invoice))).scalar_one()
    )
    total_recent = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Invoice)
                .where(Invoice.created_at >= since)
            )
        ).scalar_one()
    )

    staged: list[PipelineStageSummary] = []
    alerts: list[str] = []
    completed_events: dict[str, int] = {"parsing": 0, "extracting": 0, "screening": 0}

    event_rows = (
        await session.execute(
            select(InvoicePipelineEvent)
            .where(
                InvoicePipelineEvent.created_at >= (since - timedelta(days=7)),
                InvoicePipelineEvent.stage.in_(("parsing", "extracting", "screening")),
                InvoicePipelineEvent.action.in_(("started", "completed")),
            )
            .order_by(InvoicePipelineEvent.invoice_id.asc(), InvoicePipelineEvent.created_at.asc())
        )
    ).scalars().all()
    for row in event_rows:
        if row.action == "completed" and row.created_at >= since:
            completed_events[row.stage] = completed_events.get(row.stage, 0) + 1

    for stage in _stage_definitions():
        in_progress = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Invoice)
                    .where(Invoice.status == stage.in_progress_status)
                )
            ).scalar_one()
        )
        failed = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Invoice)
                    .where(Invoice.status == stage.failed_status)
                )
            ).scalar_one()
        )
        stale_cutoff = now - timedelta(minutes=stage.stale_minutes)
        stuck = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Invoice)
                    .where(
                        Invoice.status == stage.in_progress_status,
                        Invoice.updated_at < stale_cutoff,
                    )
                )
            ).scalar_one()
        )
        completed_recent = int(completed_events.get(stage.name, 0))

        staged.append(
            PipelineStageSummary(
                stage=stage.name,
                in_progress=in_progress,
                stuck=stuck,
                failed=failed,
                completed_last_window=completed_recent,
            )
        )
        if stuck > 0:
            alerts.append(
                f"{stage.name}: {stuck} stuck (eldre enn {stage.stale_minutes} min)."
            )
        if failed > 0:
            alerts.append(f"{stage.name}: {failed} med feilstatus.")

    parse_pairs = _pair_stage_durations([r for r in event_rows if r.stage == "parsing"])
    extract_pairs = _pair_stage_durations([r for r in event_rows if r.stage == "extracting"])
    screen_pairs = _pair_stage_durations([r for r in event_rows if r.stage == "screening"])

    parse_values = [seconds for end, seconds in parse_pairs if end >= since]
    extract_values = [seconds for end, seconds in extract_pairs if end >= since]
    screen_values = [seconds for end, seconds in screen_pairs if end >= since]

    e2e_pairs = _pair_end_to_end_durations(event_rows)
    e2e_values = [seconds for end, seconds in e2e_pairs if end >= since]

    latencies = [
        _latency_summary("parsing_seconds", parse_values),
        _latency_summary("extracting_seconds", extract_values),
        _latency_summary("screening_seconds", screen_values),
        _latency_summary("end_to_end_seconds", e2e_values),
    ]

    screen_p95 = _percentile(screen_values, 0.95)
    if screen_p95 is not None and screen_p95 > 180:
        alerts.append(f"screening p95 er høy ({int(screen_p95)} sek).")

    return PipelineMetricsResponse(
        generated_at=now,
        lookback_hours=lookback,
        total_invoices=total_invoices,
        total_invoices_last_window=total_recent,
        staged=staged,
        latencies=latencies,
        alerts=alerts,
    )


async def list_pipeline_recovery_candidates(
    session: AsyncSession,
    *,
    stale_minutes: int = 10,
    limit: int = 100,
) -> PipelineRecoveryResponse:
    now = datetime.now(UTC)
    stale_mins = max(1, min(24 * 60, int(stale_minutes or 10)))
    query_limit = max(1, min(500, int(limit or 100)))
    stale_cutoff = now - timedelta(minutes=stale_mins)

    statuses = (
        InvoiceStatus.PARSING,
        InvoiceStatus.EXTRACTING,
        InvoiceStatus.EXTRACTED,
        InvoiceStatus.SCREENING,
        InvoiceStatus.PARSING_FAILED,
        InvoiceStatus.EXTRACTION_FAILED,
        InvoiceStatus.SCREENING_FAILED,
    )
    rows = (
        await session.execute(
            select(Invoice)
            .where(
                Invoice.status.in_(statuses),
                (
                    (Invoice.status.in_(
                        (
                            InvoiceStatus.PARSING_FAILED,
                            InvoiceStatus.EXTRACTION_FAILED,
                            InvoiceStatus.SCREENING_FAILED,
                        )
                    ))
                    | (Invoice.updated_at < stale_cutoff)
                ),
            )
            .order_by(Invoice.updated_at.asc())
            .limit(query_limit)
        )
    ).scalars().all()

    items: list[PipelineRecoveryItem] = []
    for invoice in rows:
        reason: str | None = None
        if invoice.status == InvoiceStatus.PARSING_FAILED:
            reason = invoice.parsing_error
        elif invoice.status == InvoiceStatus.EXTRACTION_FAILED:
            reason = invoice.extraction_error
        elif invoice.status == InvoiceStatus.SCREENING_FAILED:
            reason = "Screening feilet eller timet ut."
        elif invoice.status == InvoiceStatus.EXTRACTED:
            reason = "Ekstrahert, men ikke screenet ennå."
        else:
            reason = "In-progress status over stale-grense."

        items.append(
            PipelineRecoveryItem(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                original_filename=invoice.original_filename,
                status=invoice.status.value,
                compliance_score=(
                    invoice.compliance_score.value if invoice.compliance_score else None
                ),
                updated_at=invoice.updated_at,
                minutes_in_status=_minutes_since(now, invoice.updated_at),
                reason=(reason[:400] if reason else None),
            )
        )

    return PipelineRecoveryResponse(
        generated_at=now,
        stale_minutes=stale_mins,
        total=len(items),
        items=items,
    )


async def get_invoice_for_recovery(
    session: AsyncSession,
    invoice_id: uuid.UUID,
) -> Invoice | None:
    return await session.get(Invoice, invoice_id)
