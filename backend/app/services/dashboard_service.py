"""Dashboard-tjeneste — KPI-er og statistikk for compliance-offiseren.

Returnerer aggregerte tall om:
  - Invoices behandlet per uke/måned
  - Åpne flagg per kategori (red/yellow/green)
  - Gjennomsnittlig behandlingstid (upload → screened)
  - Trend over tid (siste 8 uker)
  - Topp 5 kunder med flest flagg
  - Sanksjonsscreening-statistikk
  - Regelmotor-statistikk
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.invoice import ComplianceScore, Invoice, InvoiceStatus
from app.models.screening import MatchStatus, ScreeningResult

logger = get_logger(__name__)


async def get_dashboard(session: AsyncSession) -> dict[str, Any]:
    """Bygg komplett dashboard-payload."""
    now = datetime.now(tz=UTC)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    results = await _run_queries(session, now, week_ago, month_ago)
    return results


async def _run_queries(
    session: AsyncSession,
    now: datetime,
    week_ago: datetime,
    month_ago: datetime,
) -> dict[str, Any]:
    # ── Totaltall ──────────────────────────────────────────────────────────────
    total_stmt = select(func.count(Invoice.id))
    total_result = await session.execute(total_stmt)
    total_invoices: int = total_result.scalar_one() or 0

    # Siste 7 dager
    week_stmt = select(func.count(Invoice.id)).where(Invoice.created_at >= week_ago)
    week_result = await session.execute(week_stmt)
    invoices_this_week: int = week_result.scalar_one() or 0

    # Siste 30 dager
    month_stmt = select(func.count(Invoice.id)).where(Invoice.created_at >= month_ago)
    month_result = await session.execute(month_stmt)
    invoices_this_month: int = month_result.scalar_one() or 0

    # ── Score-fordeling ────────────────────────────────────────────────────────
    score_stmt = select(Invoice.compliance_score, func.count(Invoice.id).label("cnt")).group_by(
        Invoice.compliance_score
    )
    score_result = await session.execute(score_stmt)
    score_dist: dict[str, int] = {"green": 0, "yellow": 0, "red": 0, "unknown": 0}
    for row in score_result:
        key = row.compliance_score.value if row.compliance_score else "unknown"
        score_dist[key] = row.cnt

    # Åpne flagg = invoices som ikke er approved/blocked og har score yellow/red
    open_flags_stmt = select(func.count(Invoice.id)).where(
        Invoice.compliance_score.in_([ComplianceScore.YELLOW, ComplianceScore.RED]),
        Invoice.status.not_in([InvoiceStatus.APPROVED, InvoiceStatus.BLOCKED]),
    )
    open_flags_result = await session.execute(open_flags_stmt)
    open_flags: int = open_flags_result.scalar_one() or 0

    # ── Ukentlig trend (siste 8 uker) ─────────────────────────────────────────
    weekly_trend = await _weekly_trend(session, now, weeks=8)

    # ── Gjennomsnittlig behandlingstid ────────────────────────────────────────
    # Fra opprettelse til SCREENED-status (tilnærming via updated_at når screened)
    avg_time_stmt = select(func.avg(func.extract("epoch", Invoice.updated_at - Invoice.created_at))).where(
        Invoice.status.in_(
            [
                InvoiceStatus.SCREENED,
                InvoiceStatus.REVIEWED,
                InvoiceStatus.APPROVED,
                InvoiceStatus.BLOCKED,
            ]
        )
    )
    avg_time_result = await session.execute(avg_time_stmt)
    avg_seconds = avg_time_result.scalar_one()
    avg_processing_seconds: float = round(float(avg_seconds), 1) if avg_seconds else 0.0

    # ── Topp 5 kunder med flest flagg ─────────────────────────────────────────
    top_customers = await _top_customers_with_flags(session, month_ago)

    # ── Sanksjons-statistikk ─────────────────────────────────────────────────
    sanctions_stats = await _sanctions_stats(session, month_ago)

    # ── Status-fordeling ──────────────────────────────────────────────────────
    status_stmt = select(Invoice.status, func.count(Invoice.id).label("cnt")).group_by(Invoice.status)
    status_result = await session.execute(status_stmt)
    status_dist = {row.status.value: row.cnt for row in status_result}

    # ── Audit-aktivitet (siste 7 dager) ───────────────────────────────────────
    audit_stmt = (
        select(AuditLog.action, func.count(AuditLog.id).label("cnt"))
        .where(AuditLog.created_at >= week_ago)
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
        .limit(10)
    )
    audit_result = await session.execute(audit_stmt)
    recent_audit_actions = [{"action": row.action, "count": row.cnt} for row in audit_result]

    return {
        "generated_at": now.isoformat(),
        "totals": {
            "invoices_total": total_invoices,
            "invoices_this_week": invoices_this_week,
            "invoices_this_month": invoices_this_month,
            "open_flags": open_flags,
            "avg_processing_seconds": avg_processing_seconds,
        },
        "score_distribution": score_dist,
        "status_distribution": status_dist,
        "weekly_trend": weekly_trend,
        "top_customers_with_flags": top_customers,
        "sanctions": sanctions_stats,
        "recent_audit_actions": recent_audit_actions,
    }


async def _weekly_trend(
    session: AsyncSession,
    now: datetime,
    weeks: int = 8,
) -> list[dict[str, Any]]:
    """Hent antall invoices og flagg per uke de siste N ukene."""
    # Vi bruker trunc til uke i PostgreSQL
    stmt = text("""
        SELECT
            date_trunc('week', created_at AT TIME ZONE 'UTC') AS week_start,
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE compliance_score = 'red') AS red_flags,
            COUNT(*) FILTER (WHERE compliance_score = 'yellow') AS yellow_flags,
            COUNT(*) FILTER (WHERE compliance_score = 'green') AS green_count
        FROM invoices
        WHERE created_at >= :cutoff
        GROUP BY week_start
        ORDER BY week_start ASC
    """)
    cutoff = now - timedelta(weeks=weeks)
    result = await session.execute(stmt, {"cutoff": cutoff})
    return [
        {
            "week_start": row.week_start.isoformat() if row.week_start else None,
            "total": row.total,
            "red_flags": row.red_flags,
            "yellow_flags": row.yellow_flags,
            "green_count": row.green_count,
        }
        for row in result
    ]


async def _top_customers_with_flags(
    session: AsyncSession,
    since: datetime,
) -> list[dict[str, Any]]:
    """Topp 5 kunder med flest flaggede invoices (yellow + red)."""
    stmt = (
        select(
            Customer.id,
            Customer.name,
            func.count(Invoice.id).label("flag_count"),
        )
        .join(Invoice, Invoice.customer_id == Customer.id)
        .where(
            Invoice.compliance_score.in_([ComplianceScore.YELLOW, ComplianceScore.RED]),
            Invoice.created_at >= since,
        )
        .group_by(Customer.id, Customer.name)
        .order_by(func.count(Invoice.id).desc())
        .limit(5)
    )
    result = await session.execute(stmt)
    return [{"customer_id": str(row.id), "customer_name": row.name, "flag_count": row.flag_count} for row in result]


async def _sanctions_stats(
    session: AsyncSession,
    since: datetime,
) -> dict[str, Any]:
    """Statistikk over sanksjonsscreening."""
    total_stmt = select(func.count(ScreeningResult.id)).where(ScreeningResult.screened_at >= since)
    total_result = await session.execute(total_stmt)
    total_screenings: int = total_result.scalar_one() or 0

    confirmed_stmt = select(func.count(ScreeningResult.id)).where(
        ScreeningResult.screened_at >= since,
        ScreeningResult.status == MatchStatus.CONFIRMED_MATCH,
    )
    confirmed_result = await session.execute(confirmed_stmt)
    confirmed: int = confirmed_result.scalar_one() or 0

    potential_stmt = select(func.count(ScreeningResult.id)).where(
        ScreeningResult.screened_at >= since,
        ScreeningResult.status == MatchStatus.POTENTIAL_MATCH,
    )
    potential_result = await session.execute(potential_stmt)
    potential: int = potential_result.scalar_one() or 0

    return {
        "total_screenings_this_month": total_screenings,
        "confirmed_matches": confirmed,
        "potential_matches": potential,
    }
