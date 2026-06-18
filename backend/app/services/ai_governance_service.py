"""AI Governance — registrering og visning av AI-beslutninger.

Upsert-strategi: PostgreSQL INSERT ... ON CONFLICT (invoice_id) DO UPDATE
sørger for at det aldri eksisterer mer enn én rad per faktura, selv ved
gjentatte re-ekstraksjonskjøringer.

EU AI Act-klassifisering:
  Systemet vurderes som «limited_risk» som standard (Article 52 — gjennomsiktighetsplikt).
  Dersom systemet i fremtiden fatter autonome blokkerings-beslutninger uten
  menneskelig overstyring, bør kategorien oppgraderes til «high_risk» (Annex III).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.ai_decision_record import AIDecisionRecord

logger = get_logger(__name__)

# Standard EU AI Act-kategorisering for dette systemet
_DEFAULT_EU_CATEGORY = "limited_risk"
_DEFAULT_ANNEX_III = None
_REQUIRES_HUMAN_OVERSIGHT = True


async def upsert_decision_record(
    session: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    model_id: str,
    model_provider: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    overall_confidence: float | None = None,
    low_confidence_fields: list[str] | None = None,
    raw_extraction_meta: dict | None = None,
    eu_ai_act_category: str = _DEFAULT_EU_CATEGORY,
) -> None:
    """Opprett eller oppdater AI-beslutningspost for en invoice.

    Bruker PostgreSQL ON CONFLICT DO UPDATE for idempotent upsert.
    """
    low_conf_str = ", ".join(low_confidence_fields) if low_confidence_fields else None
    now = datetime.now(UTC)

    stmt = (
        pg_insert(AIDecisionRecord)
        .values(
            id=uuid.uuid4(),
            invoice_id=invoice_id,
            model_id=model_id[:128],
            model_provider=model_provider[:64],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            overall_confidence=overall_confidence,
            low_confidence_fields=low_conf_str,
            eu_ai_act_category=eu_ai_act_category[:32],
            annex_iii_class=_DEFAULT_ANNEX_III,
            requires_human_oversight=_REQUIRES_HUMAN_OVERSIGHT,
            decision_at=now,
            raw_extraction_meta=raw_extraction_meta,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_update(
            index_elements=["invoice_id"],
            set_={
                "model_id": model_id[:128],
                "model_provider": model_provider[:64],
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "overall_confidence": overall_confidence,
                "low_confidence_fields": low_conf_str,
                "eu_ai_act_category": eu_ai_act_category[:32],
                "decision_at": now,
                "raw_extraction_meta": raw_extraction_meta,
                "updated_at": now,
            },
        )
    )
    await session.execute(stmt)
    logger.debug(
        "ai_decision_record_upserted",
        invoice_id=str(invoice_id),
        model_id=model_id,
    )


async def get_record(session: AsyncSession, invoice_id: uuid.UUID) -> AIDecisionRecord | None:
    result = await session.execute(select(AIDecisionRecord).where(AIDecisionRecord.invoice_id == invoice_id))
    return result.scalar_one_or_none()


async def list_records(
    session: AsyncSession,
    *,
    eu_ai_act_category: str | None = None,
    model_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AIDecisionRecord], int]:
    base = select(AIDecisionRecord)
    if eu_ai_act_category:
        base = base.where(AIDecisionRecord.eu_ai_act_category == eu_ai_act_category)
    if model_id:
        base = base.where(AIDecisionRecord.model_id == model_id)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    rows = list(
        (await session.execute(base.order_by(AIDecisionRecord.decision_at.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return rows, total


async def governance_summary(session: AsyncSession) -> dict:
    """Aggregert oversikt for EU AI Act-rapportering."""
    result = await session.execute(
        select(
            AIDecisionRecord.eu_ai_act_category,
            AIDecisionRecord.model_id,
            func.count(AIDecisionRecord.id).label("count"),
            func.avg(AIDecisionRecord.overall_confidence).label("avg_confidence"),
            func.sum(AIDecisionRecord.input_tokens).label("total_input_tokens"),
            func.sum(AIDecisionRecord.output_tokens).label("total_output_tokens"),
        )
        .group_by(AIDecisionRecord.eu_ai_act_category, AIDecisionRecord.model_id)
        .order_by(AIDecisionRecord.eu_ai_act_category, AIDecisionRecord.model_id)
    )
    rows = result.all()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "by_category_and_model": [
            {
                "eu_ai_act_category": row.eu_ai_act_category,
                "model_id": row.model_id,
                "count": row.count,
                "avg_confidence": round(float(row.avg_confidence or 0), 4),
                "total_input_tokens": int(row.total_input_tokens or 0),
                "total_output_tokens": int(row.total_output_tokens or 0),
            }
            for row in rows
        ],
        "requires_human_oversight": _REQUIRES_HUMAN_OVERSIGHT,
        "eu_ai_act_article": "Article 52 (limited risk) — gjennomsiktighetsplikt",
    }
