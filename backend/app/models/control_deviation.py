"""Control Effectiveness — registrerer avvik fra compliance-kontrollene.

En avvikspost opprettes når en invoice godkjennes til tross for YELLOW
eller RED compliance-score.  Over tid gir disse postene målbart grunnlag
for å vurdere om kontrollene faktisk fungerer (KRI: false positive rate,
gjentatte leverandøravvik osv.).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class ControlDeviation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Én post per gang en invoice godkjennes med forhøyet compliance-score."""

    __tablename__ = "control_deviations"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Score da avviket ble registrert ("yellow" | "red")
    compliance_score_at_approval: Mapped[str] = mapped_column(String(16), nullable=False)

    # Hvem godkjente
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)

    # Avvikstype: "approved_despite_yellow" | "approved_despite_red"
    deviation_type: Mapped[str] = mapped_column(String(64), nullable=False)

    # Normalisert leverandørnavn (sist sett SELLER/BUYER/CONSIGNOR fra invoice)
    vendor_name: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Landkode fra destination_country
    destination_country: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Ble det oppdaget at denne leverandøren har hatt tidligere avvik?
    is_repeat_vendor: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Begrunnelse kopiert fra review_reason
    reason_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    invoice: Mapped[Invoice] = relationship("Invoice")

    __table_args__ = (
        Index("ix_control_deviations_invoice_id", "invoice_id"),
        Index("ix_control_deviations_deviation_type", "deviation_type"),
        Index("ix_control_deviations_vendor_name", "vendor_name"),
        Index("ix_control_deviations_is_repeat_vendor", "is_repeat_vendor"),
    )
