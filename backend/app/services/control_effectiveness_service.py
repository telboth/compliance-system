"""Control Effectiveness — registrering og analyse av godkjennings-avvik.

Avvik registreres når en invoice godkjennes («approved») til tross for at
compliance_score er YELLOW eller RED.  Gjentatte avvik fra samme leverandør
flagges automatisk (is_repeat_vendor=True) og utløser et ekstra varsel.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.control_deviation import ControlDeviation
from app.models.entity import EntityRole
from app.models.invoice import ComplianceScore, Invoice
from app.services import notification_service

logger = get_logger(__name__)

# Roller som regnes som "primær part" for leverandøridentifikasjon
_PRIMARY_VENDOR_ROLES = {EntityRole.SELLER, EntityRole.CONSIGNOR, EntityRole.BUYER}


def _deviation_type(score: ComplianceScore) -> str:
    if score == ComplianceScore.RED:
        return "approved_despite_red"
    return "approved_despite_yellow"


async def _find_primary_vendor_name(invoice: Invoice) -> str | None:
    """Plukk ut normalisert navn på SELLER/CONSIGNOR/BUYER fra lastet invoice."""
    for role in (EntityRole.SELLER, EntityRole.CONSIGNOR, EntityRole.BUYER):
        for entity in (invoice.entities or []):
            if entity.role == role and entity.name:
                return entity.name.strip().lower()
    return None


async def _count_previous_deviations(
    session: AsyncSession,
    *,
    vendor_name: str,
    exclude_invoice_id: object,
) -> int:
    """Tell avviksposter for samme leverandørnavn (unntatt nåværende faktura)."""
    from sqlalchemy import func
    result = await session.execute(
        select(func.count(ControlDeviation.id)).where(
            ControlDeviation.vendor_name == vendor_name,
            ControlDeviation.invoice_id != exclude_invoice_id,
        )
    )
    return result.scalar_one() or 0


async def record_deviation_if_applicable(
    session: AsyncSession,
    *,
    invoice: Invoice,
    reviewed_by: str,
    reason_summary: str | None = None,
) -> ControlDeviation | None:
    """Registrer avvik dersom invoicen godkjennes med YELLOW eller RED score.

    Returnerer ControlDeviation-instansen om det ble registrert, ellers None.
    """
    if invoice.compliance_score not in (ComplianceScore.YELLOW, ComplianceScore.RED):
        return None

    vendor_name = await _find_primary_vendor_name(invoice)
    is_repeat = False

    if vendor_name:
        prev_count = await _count_previous_deviations(
            session,
            vendor_name=vendor_name,
            exclude_invoice_id=invoice.id,
        )
        is_repeat = prev_count > 0

    deviation = ControlDeviation(
        invoice_id=invoice.id,
        compliance_score_at_approval=invoice.compliance_score.value,
        reviewed_by=reviewed_by,
        deviation_type=_deviation_type(invoice.compliance_score),
        vendor_name=vendor_name,
        destination_country=invoice.destination_country,
        is_repeat_vendor=is_repeat,
        reason_summary=(reason_summary or "")[:2000] or None,
    )
    session.add(deviation)
    await session.flush()

    logger.info(
        "control_deviation_recorded",
        invoice_id=str(invoice.id),
        deviation_type=deviation.deviation_type,
        vendor_name=vendor_name,
        is_repeat=is_repeat,
    )

    # Ekstra varsel ved gjentatt leverandøravvik
    if is_repeat and vendor_name:
        inv_label = invoice.original_filename or invoice.invoice_number or str(invoice.id)[:8]
        await notification_service.create(
            session,
            message=(
                f"⚠️ Gjentatt avvik: {vendor_name!r} er godkjent med "
                f"{invoice.compliance_score.value.upper()} score igjen ({inv_label})"
            ),
            level="warn",
            invoice_id=invoice.id,
            target_roles=["compliance_officer", "admin"],
        )

    return deviation


async def list_deviations(
    session: AsyncSession,
    *,
    deviation_type: str | None = None,
    is_repeat_vendor: bool | None = None,
    vendor_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ControlDeviation], int]:
    base = select(ControlDeviation)
    if deviation_type:
        base = base.where(ControlDeviation.deviation_type == deviation_type)
    if is_repeat_vendor is not None:
        base = base.where(ControlDeviation.is_repeat_vendor == is_repeat_vendor)
    if vendor_name:
        base = base.where(
            ControlDeviation.vendor_name.ilike(f"%{vendor_name.lower()}%")
        )

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = list(
        (
            await session.execute(
                base.order_by(ControlDeviation.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return rows, total
