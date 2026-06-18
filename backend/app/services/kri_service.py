"""KRI-tjeneste (Key Risk Indicators) — aggregerte risikomålinger for compliance-dashboard.

Alle queries er ren SQL-aggregering — ingen full-table-load.

Indikatorer:
  - screening_hit_rate:     Andel screened invoices med minst ett treff
  - false_positive_rate:    Andel treff som ble godkjent (potential_match + approved)
  - avg_days_to_resolution: Snittid fra SCREENED til reviewed_at
  - top_flagged_countries:  Land med flest screening-treff (embargo + entity)
  - top_flagged_entities:   Entiteter med flest confirmed/potential matches
  - risk_exposure_total_nok: Sum eksponering for screened invoices (NOK)
  - monthly_hit_trend:      Antall treff per måned siste 12 mnd
"""

from __future__ import annotations

import csv
import io
from collections.abc import Awaitable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.invoice import ComplianceScore, Invoice, InvoiceStatus
from app.models.screening import MatchStatus, ScreeningResult

logger = get_logger(__name__)

_T = TypeVar("_T")


# ---------------------------------------------------------------------------
# Hjelp
# ---------------------------------------------------------------------------


def _months_back(n: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=30 * n)


# ---------------------------------------------------------------------------
# Enkelt-KRI-beregninger
# ---------------------------------------------------------------------------


async def screening_hit_rate(session: AsyncSession, *, months: int = 12) -> dict:
    """Andel screened invoices med minst ett potential/confirmed treff."""
    since = _months_back(months)
    total_q = await session.execute(
        select(func.count(Invoice.id)).where(
            Invoice.status == InvoiceStatus.SCREENED,
            Invoice.created_at >= since,
        )
    )
    total: int = total_q.scalar_one() or 0

    hit_q = await session.execute(
        select(func.count(Invoice.id.distinct())).where(
            Invoice.status == InvoiceStatus.SCREENED,
            Invoice.created_at >= since,
            Invoice.compliance_score.in_([ComplianceScore.YELLOW, ComplianceScore.RED]),
        )
    )
    with_hits: int = hit_q.scalar_one() or 0

    rate = round(with_hits / total, 4) if total else 0.0
    return {"total_screened": total, "with_hits": with_hits, "rate": rate}


async def false_positive_rate(session: AsyncSession, *, months: int = 12) -> dict:
    """Andel potential_match-treff som endte med 'approved' review-beslutning."""
    since = _months_back(months)

    # Potential matches (YELLOW) som er reviewed
    potential_q = await session.execute(
        select(func.count(Invoice.id)).where(
            Invoice.compliance_score == ComplianceScore.YELLOW,
            Invoice.reviewed_at.is_not(None),
            Invoice.created_at >= since,
        )
    )
    potential: int = potential_q.scalar_one() or 0

    approved_q = await session.execute(
        select(func.count(Invoice.id)).where(
            Invoice.compliance_score == ComplianceScore.YELLOW,
            Invoice.review_decision == "approved",
            Invoice.reviewed_at.is_not(None),
            Invoice.created_at >= since,
        )
    )
    approved: int = approved_q.scalar_one() or 0

    rate = round(approved / potential, 4) if potential else 0.0
    return {"potential_reviewed": potential, "false_positives": approved, "rate": rate}


async def avg_days_to_resolution(session: AsyncSession, *, months: int = 12) -> dict:
    """Snittid fra status=SCREENED (via screened_at) til reviewed_at."""
    since = _months_back(months)

    result = await session.execute(
        select(
            func.avg(func.extract("epoch", Invoice.reviewed_at - Invoice.updated_at) / 86400.0).label("avg_days")
        ).where(
            Invoice.reviewed_at.is_not(None),
            Invoice.review_decision.is_not(None),
            Invoice.created_at >= since,
        )
    )
    avg_days_raw = result.scalar_one()
    avg_days = round(float(avg_days_raw), 2) if avg_days_raw is not None else None
    return {"avg_days_to_resolution": avg_days, "months": months}


async def top_flagged_countries(session: AsyncSession, *, limit: int = 10, months: int = 12) -> list[dict]:
    """Land (destination_country) med flest screening-treff."""
    since = _months_back(months)

    # Join via Invoice.destination_country
    result = await session.execute(
        select(
            Invoice.destination_country.label("country"),
            func.count(ScreeningResult.id).label("hit_count"),
        )
        .join(Invoice, ScreeningResult.invoice_id == Invoice.id)
        .where(
            Invoice.destination_country.is_not(None),
            ScreeningResult.status.in_([MatchStatus.CONFIRMED_MATCH, MatchStatus.POTENTIAL_MATCH]),
            ScreeningResult.screened_at >= since,
        )
        .group_by(Invoice.destination_country)
        .order_by(func.count(ScreeningResult.id).desc())
        .limit(limit)
    )
    return [{"country": row.country, "hit_count": row.hit_count} for row in result]


async def top_flagged_entities(session: AsyncSession, *, limit: int = 10, months: int = 12) -> list[dict]:
    """Entitetsnavn med flest confirmed/potential matches."""
    since = _months_back(months)

    result = await session.execute(
        select(
            ScreeningResult.matched_name.label("entity_name"),
            func.count(ScreeningResult.id).label("hit_count"),
            func.sum(
                case(
                    (ScreeningResult.status == MatchStatus.CONFIRMED_MATCH, 1),
                    else_=0,
                )
            ).label("confirmed_count"),
        )
        .where(
            ScreeningResult.matched_name.is_not(None),
            ScreeningResult.status.in_([MatchStatus.CONFIRMED_MATCH, MatchStatus.POTENTIAL_MATCH]),
            ScreeningResult.screened_at >= since,
        )
        .group_by(ScreeningResult.matched_name)
        .order_by(func.count(ScreeningResult.id).desc())
        .limit(limit)
    )
    return [
        {
            "entity_name": row.entity_name,
            "hit_count": row.hit_count,
            "confirmed_count": int(row.confirmed_count or 0),
        }
        for row in result
    ]


async def risk_exposure_summary(session: AsyncSession) -> dict:
    """Sum og gjennomsnitt av risk_exposure_nok for screened invoices."""
    result = await session.execute(
        select(
            func.sum(Invoice.risk_exposure_nok).label("total_nok"),
            func.avg(Invoice.risk_exposure_nok).label("avg_nok"),
            func.count(Invoice.id).label("count"),
        ).where(
            Invoice.risk_exposure_nok.is_not(None),
        )
    )
    row = result.one()
    return {
        "total_exposure_nok": float(row.total_nok or 0),
        "avg_exposure_nok": round(float(row.avg_nok or 0), 2),
        "invoice_count": row.count,
    }


async def monthly_hit_trend(session: AsyncSession, *, months: int = 12) -> list[dict]:
    """Antall screeningtreff gruppert per måned, siste N måneder."""
    since = _months_back(months)

    # Bygg trunkeringsuttrykket ÉN gang og gjenbruk samme objekt i select,
    # group_by og order_by. Tre separate func.date_trunc(...)-kall ville gitt
    # ulike bind-parametre, som Postgres ikke gjenkjenner som samme uttrykk
    # (GroupingError: "must appear in the GROUP BY clause").
    month_col = func.date_trunc("month", ScreeningResult.screened_at)

    result = await session.execute(
        select(
            month_col.label("month"),
            func.count(ScreeningResult.id).label("hit_count"),
            func.sum(
                case(
                    (ScreeningResult.status == MatchStatus.CONFIRMED_MATCH, 1),
                    else_=0,
                )
            ).label("confirmed_count"),
        )
        .where(
            ScreeningResult.screened_at >= since,
            ScreeningResult.status.in_([MatchStatus.CONFIRMED_MATCH, MatchStatus.POTENTIAL_MATCH]),
        )
        .group_by(month_col)
        .order_by(month_col)
    )
    return [
        {
            "month": row.month.strftime("%Y-%m") if row.month else None,
            "hit_count": row.hit_count,
            "confirmed_count": int(row.confirmed_count or 0),
        }
        for row in result
    ]


# ---------------------------------------------------------------------------
# Komplett KRI-rapport
# ---------------------------------------------------------------------------


async def _safe(coro: Awaitable[_T], *, default: _T, name: str) -> _T:
    """Kjør én KRI-indikator; ved feil logges den og en trygg standard returneres.

    Gjør at én feilende indikator ikke 500-er hele dashbordet — resten lastes,
    og loggen navngir hvilken del som feilet.
    """
    try:
        return await coro
    except Exception:
        logger.exception("kri_indicator_failed", indicator=name)
        return default


async def full_kri_report(session: AsyncSession, *, months: int = 12) -> dict:
    """Samle alle KRI-er i én respons. Robust: delvis data ved enkeltfeil."""
    empty_rate = {"total_screened": 0, "with_hits": 0, "rate": 0.0}
    empty_fp = {"potential_reviewed": 0, "false_positives": 0, "rate": 0.0}
    empty_avg: dict[str, Any] = {"avg_days_to_resolution": None, "months": months}
    empty_exposure = {"total_exposure_nok": 0.0, "avg_exposure_nok": 0.0, "invoice_count": 0}
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "period_months": months,
        "screening_hit_rate": await _safe(
            screening_hit_rate(session, months=months),
            default=empty_rate,
            name="screening_hit_rate",
        ),
        "false_positive_rate": await _safe(
            false_positive_rate(session, months=months),
            default=empty_fp,
            name="false_positive_rate",
        ),
        "avg_days_to_resolution": await _safe(
            avg_days_to_resolution(session, months=months),
            default=empty_avg,
            name="avg_days_to_resolution",
        ),
        "top_flagged_countries": await _safe(
            top_flagged_countries(session, months=months), default=[], name="top_flagged_countries"
        ),
        "top_flagged_entities": await _safe(
            top_flagged_entities(session, months=months), default=[], name="top_flagged_entities"
        ),
        "risk_exposure_summary": await _safe(
            risk_exposure_summary(session), default=empty_exposure, name="risk_exposure_summary"
        ),
        "monthly_hit_trend": await _safe(
            monthly_hit_trend(session, months=months), default=[], name="monthly_hit_trend"
        ),
    }


# ---------------------------------------------------------------------------
# CSV-eksport
# ---------------------------------------------------------------------------


def kri_to_csv(report: dict) -> str:
    """Konverter KRI-rapport til CSV-streng (flat format, én seksjon per rad-gruppe)."""
    buf = io.StringIO()
    w = csv.writer(buf)

    w.writerow(
        [
            "KRI-rapport",
            f"Generert: {report.get('generated_at', '')}",
            f"Periode: {report.get('period_months', 12)} mnd",
        ]
    )
    w.writerow([])

    # Screening hit rate
    hr = report.get("screening_hit_rate", {})
    w.writerow(["Screening hit rate"])
    w.writerow(["Total screened", "Med treff", "Rate"])
    w.writerow([hr.get("total_screened"), hr.get("with_hits"), hr.get("rate")])
    w.writerow([])

    # False positive rate
    fpr = report.get("false_positive_rate", {})
    w.writerow(["False positive rate"])
    w.writerow(["Potential reviewed", "Godkjente (FP)", "Rate"])
    w.writerow([fpr.get("potential_reviewed"), fpr.get("false_positives"), fpr.get("rate")])
    w.writerow([])

    # Avg days
    avd = report.get("avg_days_to_resolution", {})
    w.writerow(["Snittid til beslutning (dager)"])
    w.writerow([avd.get("avg_days_to_resolution")])
    w.writerow([])

    # Top countries
    w.writerow(["Topp flaggede land"])
    w.writerow(["Land", "Treff"])
    for row in report.get("top_flagged_countries", []):
        w.writerow([row["country"], row["hit_count"]])
    w.writerow([])

    # Top entities
    w.writerow(["Topp flaggede entiteter"])
    w.writerow(["Entitetsnavn", "Treff", "Confirmed"])
    for row in report.get("top_flagged_entities", []):
        w.writerow([row["entity_name"], row["hit_count"], row["confirmed_count"]])
    w.writerow([])

    # Exposure
    exp = report.get("risk_exposure_summary", {})
    w.writerow(["Risikoeksponering (NOK)"])
    w.writerow(["Total NOK", "Snitt NOK", "Antall fakturaer"])
    w.writerow([exp.get("total_exposure_nok"), exp.get("avg_exposure_nok"), exp.get("invoice_count")])
    w.writerow([])

    # Monthly trend
    w.writerow(["Månedlig trenddata"])
    w.writerow(["Måned", "Treff", "Confirmed"])
    for row in report.get("monthly_hit_trend", []):
        w.writerow([row["month"], row["hit_count"], row["confirmed_count"]])

    return buf.getvalue()
