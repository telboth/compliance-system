"""Review/claim/queue-logikk for invoices."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import ApplicationError, NotFoundError
from app.models.invoice import ApprovalState, ComplianceScore, Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceLine
from app.models.screening import MatchStatus, ScreeningResult
from app.schemas.invoice import ReviewQueueItem, ReviewQueueResponse
from app.services import audit_service

REVIEWABLE_STATUSES = {
    InvoiceStatus.SCREENED,
    InvoiceStatus.APPROVED,
    InvoiceStatus.BLOCKED,
}


class ReviewClaimConflictError(ApplicationError):
    status_code = 409
    code = "REVIEW_CLAIM_CONFLICT"


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _claim_is_stale(invoice: Invoice, now: datetime, stale_minutes: int) -> bool:
    if not invoice.review_claimed_by:
        return False
    if invoice.review_claimed_at is None:
        return True
    claimed_at = (
        invoice.review_claimed_at
        if invoice.review_claimed_at.tzinfo is not None
        else invoice.review_claimed_at.replace(tzinfo=UTC)
    )
    return claimed_at <= (now - timedelta(minutes=max(1, stale_minutes)))


def _clear_review_claim(invoice: Invoice) -> None:
    invoice.review_claimed_by = None
    invoice.review_claimed_at = None


def _review_claim_stale_minutes() -> int:
    return max(1, int(get_settings().review_claim_stale_minutes))


def _compose_review_reason(
    *,
    reason: str,
    rule_reference: str,
    evidence_summary: str,
    deviation_approval: bool,
) -> str:
    deviation_text = "Ja" if deviation_approval else "Nei"
    return (
        f"Begrunnelse: {reason.strip()}\n"
        f"Regelreferanse: {rule_reference.strip()}\n"
        f"Evidens: {evidence_summary.strip()}\n"
        f"Avviksgodkjenning: {deviation_text}"
    )


async def _get_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Invoice:
    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.lines), selectinload(Invoice.entities))
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise NotFoundError(
            "Invoice ikke funnet.",
            details={"invoice_id": str(invoice_id)},
        )
    return invoice


async def _apply_review_decision(
    session: AsyncSession,
    *,
    invoice: Invoice,
    decision: str,
    reason: str,
    rule_reference: str,
    evidence_summary: str,
    deviation_approval: bool,
    actor: str,
) -> None:
    if invoice.status not in REVIEWABLE_STATUSES:
        raise ApplicationError(
            f"Kan ikke reviewe en invoice med status '{invoice.status.value}'. Invoicen må være screenet først.",
            details={"invoice_id": str(invoice.id), "status": invoice.status.value},
        )

    prev_status = invoice.status.value
    invoice.status = InvoiceStatus.APPROVED if decision == "approved" else InvoiceStatus.BLOCKED
    invoice.review_decision = decision
    invoice.review_reason = _compose_review_reason(
        reason=reason,
        rule_reference=rule_reference,
        evidence_summary=evidence_summary,
        deviation_approval=deviation_approval,
    )
    invoice.reviewed_by = actor
    invoice.reviewed_at = _now_utc()
    _clear_review_claim(invoice)

    await audit_service.log(
        session,
        action=f"invoice.{decision}",
        actor=actor,
        invoice_id=invoice.id,
        details={
            "decision": decision,
            "reason": reason,
            "rule_reference": rule_reference,
            "evidence_summary": evidence_summary,
            "deviation_approval": deviation_approval,
            "prev_status": prev_status,
        },
    )

    from app.services import control_effectiveness_service as ce_svc
    from app.services import notification_service

    inv_label = invoice.original_filename or invoice.invoice_number or str(invoice.id)[:8]
    decision_icon = "✓" if decision == "approved" else "🔒"
    await notification_service.create(
        session,
        message=(f"{decision_icon} {inv_label} ble {'godkjent' if decision == 'approved' else 'blokkert'} av {actor}"),
        level="info" if decision == "approved" else "warn",
        invoice_id=invoice.id,
        target_roles=["controller", "admin"],
    )

    # Control Effectiveness: registrer avvik dersom godkjent med forhøyet score
    if decision == "approved":
        try:
            await ce_svc.record_deviation_if_applicable(
                session,
                invoice=invoice,
                reviewed_by=actor,
                reason_summary=reason,
            )
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "control_deviation_record_failed", extra={"invoice_id": str(invoice.id)}
            )


async def _find_next_review_invoice_to_claim(
    session: AsyncSession,
    *,
    actor: str,
    exclude_invoice_id: uuid.UUID | None = None,
    stale_minutes: int,
) -> Invoice | None:
    stale_cutoff = _now_utc() - timedelta(minutes=max(1, stale_minutes))

    severity_order = case(
        (Invoice.compliance_score == ComplianceScore.RED, 0),
        (Invoice.compliance_score == ComplianceScore.YELLOW, 1),
        else_=2,
    )

    stmt = (
        select(Invoice)
        .where(
            Invoice.status == InvoiceStatus.SCREENED,
            Invoice.compliance_score.in_((ComplianceScore.RED, ComplianceScore.YELLOW)),
            Invoice.approval_state == ApprovalState.PENDING,
            or_(
                Invoice.review_claimed_by.is_(None),
                Invoice.review_claimed_by == actor,
                Invoice.review_claimed_at.is_(None),
                Invoice.review_claimed_at < stale_cutoff,
            ),
        )
        .order_by(severity_order, Invoice.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if exclude_invoice_id is not None:
        stmt = stmt.where(Invoice.id != exclude_invoice_id)

    return (await session.execute(stmt)).scalar_one_or_none()


async def review_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    decision: str,
    reason: str,
    rule_reference: str,
    evidence_summary: str,
    deviation_approval: bool,
    actor: str = "system",
) -> Invoice:
    invoice = await _get_invoice(session, invoice_id, for_update=True)
    stale_minutes = _review_claim_stale_minutes()
    now = _now_utc()
    if (
        invoice.review_claimed_by
        and invoice.review_claimed_by != actor
        and not _claim_is_stale(invoice, now, stale_minutes)
    ):
        raise ReviewClaimConflictError(
            f"Invoicen er allerede claimet av {invoice.review_claimed_by}.",
            details={"invoice_id": str(invoice_id), "review_claimed_by": invoice.review_claimed_by},
        )

    await _apply_review_decision(
        session,
        invoice=invoice,
        decision=decision,
        reason=reason,
        rule_reference=rule_reference,
        evidence_summary=evidence_summary,
        deviation_approval=deviation_approval,
        actor=actor,
    )
    await session.commit()
    return await _get_invoice(session, invoice_id)


async def review_invoice_and_next(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    decision: str,
    reason: str,
    rule_reference: str,
    evidence_summary: str,
    deviation_approval: bool,
    actor: str = "system",
    stale_minutes: int | None = None,
) -> tuple[Invoice, uuid.UUID | None]:
    stale = max(1, int(stale_minutes or _review_claim_stale_minutes()))
    invoice = await _get_invoice(session, invoice_id, for_update=True)
    now = _now_utc()
    if invoice.review_claimed_by and invoice.review_claimed_by != actor and not _claim_is_stale(invoice, now, stale):
        raise ReviewClaimConflictError(
            f"Invoicen er allerede claimet av {invoice.review_claimed_by}.",
            details={"invoice_id": str(invoice_id), "review_claimed_by": invoice.review_claimed_by},
        )

    await _apply_review_decision(
        session,
        invoice=invoice,
        decision=decision,
        reason=reason,
        rule_reference=rule_reference,
        evidence_summary=evidence_summary,
        deviation_approval=deviation_approval,
        actor=actor,
    )

    next_invoice = await _find_next_review_invoice_to_claim(
        session,
        actor=actor,
        exclude_invoice_id=invoice.id,
        stale_minutes=stale,
    )
    next_id: uuid.UUID | None = None
    if next_invoice is not None:
        next_invoice.review_claimed_by = actor
        next_invoice.review_claimed_at = _now_utc()
        next_id = next_invoice.id

    await session.commit()
    reviewed = await _get_invoice(session, invoice_id)
    return reviewed, next_id


async def claim_review_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    actor: str,
    stale_minutes: int | None = None,
) -> Invoice:
    stale = max(1, int(stale_minutes or _review_claim_stale_minutes()))
    invoice = await _get_invoice(session, invoice_id, for_update=True)
    if invoice.status != InvoiceStatus.SCREENED or invoice.approval_state != ApprovalState.PENDING:
        raise ApplicationError(
            "Kun screenede invoices som venter godkjenning kan claimes.",
            details={
                "invoice_id": str(invoice_id),
                "status": invoice.status.value,
                "approval_state": invoice.approval_state.value if invoice.approval_state else None,
            },
        )

    now = _now_utc()
    if invoice.review_claimed_by and invoice.review_claimed_by != actor and not _claim_is_stale(invoice, now, stale):
        raise ReviewClaimConflictError(
            f"Invoicen er allerede claimet av {invoice.review_claimed_by}.",
            details={
                "invoice_id": str(invoice_id),
                "review_claimed_by": invoice.review_claimed_by,
                "review_claimed_at": invoice.review_claimed_at.isoformat() if invoice.review_claimed_at else None,
            },
        )

    invoice.review_claimed_by = actor
    invoice.review_claimed_at = now
    await session.commit()
    return await _get_invoice(session, invoice_id)


async def release_review_claim(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    actor: str,
    stale_minutes: int | None = None,
) -> Invoice:
    stale = max(1, int(stale_minutes or _review_claim_stale_minutes()))
    invoice = await _get_invoice(session, invoice_id, for_update=True)
    now = _now_utc()
    if invoice.review_claimed_by and invoice.review_claimed_by != actor and not _claim_is_stale(invoice, now, stale):
        raise ReviewClaimConflictError(
            f"Invoicen er claimet av {invoice.review_claimed_by}; kan ikke frigi.",
            details={"invoice_id": str(invoice_id), "review_claimed_by": invoice.review_claimed_by},
        )
    _clear_review_claim(invoice)
    await session.commit()
    return await _get_invoice(session, invoice_id)


async def list_review_queue(
    session: AsyncSession,
    *,
    actor_name: str,
    limit: int = 100,
    offset: int = 0,
    score: ComplianceScore | None = None,
) -> ReviewQueueResponse:
    stmt = (
        select(Invoice)
        .where(
            Invoice.status.in_(
                [
                    InvoiceStatus.SCREENED,
                    InvoiceStatus.APPROVED,
                    InvoiceStatus.BLOCKED,
                ]
            )
        )
        .where(Invoice.compliance_score.in_([ComplianceScore.RED, ComplianceScore.YELLOW]))
    )
    if score is not None:
        stmt = stmt.where(Invoice.compliance_score == score)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    severity_order = case(
        (Invoice.compliance_score == ComplianceScore.RED, 0),
        (Invoice.compliance_score == ComplianceScore.YELLOW, 1),
        else_=2,
    )
    review_order = case((Invoice.status == InvoiceStatus.SCREENED, 0), else_=1)
    stmt = stmt.order_by(review_order, severity_order, Invoice.created_at.asc())
    stmt = stmt.limit(limit).offset(offset)

    invoices = list((await session.execute(stmt)).scalars().all())
    invoice_ids = [inv.id for inv in invoices]

    has_sanctions_hit: dict[uuid.UUID, bool] = dict.fromkeys(invoice_ids, False)
    has_embargo_hit: dict[uuid.UUID, bool] = dict.fromkeys(invoice_ids, False)
    has_eccn: dict[uuid.UUID, bool] = dict.fromkeys(invoice_ids, False)
    if invoice_ids:
        screening_rows = (
            await session.execute(
                select(
                    ScreeningResult.invoice_id,
                    ScreeningResult.dataset,
                ).where(
                    ScreeningResult.invoice_id.in_(invoice_ids),
                    ScreeningResult.status.in_(
                        [
                            MatchStatus.POTENTIAL_MATCH,
                            MatchStatus.CONFIRMED_MATCH,
                        ]
                    ),
                )
            )
        ).all()
        for row in screening_rows:
            iid = row[0]
            dataset = str(row[1] or "")
            if dataset == "country_embargo":
                has_embargo_hit[iid] = True
            if dataset not in {"trade_plausibility", "duplicate_invoice"}:
                has_sanctions_hit[iid] = True

        eccn_rows = (
            (
                await session.execute(
                    select(InvoiceLine.invoice_id.distinct()).where(
                        InvoiceLine.invoice_id.in_(invoice_ids),
                        InvoiceLine.eccn.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for iid in eccn_rows:
            has_eccn[iid] = True

    stale_minutes = _review_claim_stale_minutes()
    now = _now_utc()

    def _has_ownership_risk(inv: Invoice) -> bool:
        text = (inv.comments or "").lower()
        return any(token in text for token in ("ownership", "beneficial owner", "ultimate parent", "ubo"))

    return ReviewQueueResponse(
        items=[
            ReviewQueueItem(
                id=inv.id,
                invoice_number=inv.invoice_number,
                original_filename=inv.original_filename,
                direction=inv.direction,
                status=inv.status,
                compliance_score=inv.compliance_score,
                total_amount=inv.total_amount,
                currency=inv.currency,
                destination_country=inv.destination_country,
                created_at=inv.created_at,
                review_decision=inv.review_decision,
                reviewed_at=inv.reviewed_at,
                has_sanctions_hit=has_sanctions_hit.get(inv.id, False),
                has_embargo_hit=has_embargo_hit.get(inv.id, False),
                has_ownership_risk=_has_ownership_risk(inv),
                has_dual_use_risk=has_eccn.get(inv.id, False),
                has_vat_deviation=(inv.vat_note_status in {"warn", "error"}),
                has_export_control=(inv.export_control_status in {"review", "controlled"}),
                has_catch_all=(inv.catch_all_status in {"review", "controlled"}),
                awaiting_approval=((inv.approval_state.value if inv.approval_state else "") == "pending"),
                review_claimed_by=inv.review_claimed_by,
                review_claimed_at=inv.review_claimed_at,
                claim_is_mine=bool(inv.review_claimed_by and inv.review_claimed_by == actor_name),
                claim_is_stale=_claim_is_stale(inv, now, stale_minutes),
            )
            for inv in invoices
        ],
        total=total,
    )
