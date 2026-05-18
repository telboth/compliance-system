"""InvoiceLine — enkeltlinje i en invoice (vare/tjeneste)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class InvoiceLine(UUIDPrimaryKeyMixin, Base):
    """En enkelt linje i en invoice — vare, tjeneste eller gebyr."""

    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_code: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    hs_code: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    eccn: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    serial_number: Mapped[str | None] = mapped_column(String(256), nullable=True)
    model_number: Mapped[str | None] = mapped_column(String(256), nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(String(2), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_of_measure: Mapped[str | None] = mapped_column(String(32), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
