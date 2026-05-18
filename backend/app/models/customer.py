"""Customer — bedriften som mottar eller sender invoicen."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """En kunde eller motpart i en invoice.

    Inneholder grunnleggende kundedata. Knyttes til invoices via FK. Risikonivå
    settes manuelt av compliance officer og kan brukes som inngang til regelmotoren.
    """

    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    """ISO 3166-1 alpha-2 landkode (f.eks. «NO», «DE»)."""
    org_number: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    risk_level: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="normal",
    )

    invoices: Mapped[list[Invoice]] = relationship(
        back_populates="customer",
        cascade="save-update",
    )
