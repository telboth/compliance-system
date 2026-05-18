"""Entity — en part i invoicen (kjøper, selger, sluttbruker, leveringsadresse)."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.invoice import Invoice


class EntityType(str, enum.Enum):
    """Type entitet — påvirker hvilke sanksjonslister som er relevante."""

    PERSON = "person"
    COMPANY = "company"
    VESSEL = "vessel"
    AIRCRAFT = "aircraft"


class EntityRole(str, enum.Enum):
    """Hvilken rolle entiteten har i transaksjonen."""

    SELLER = "seller"
    BUYER = "buyer"
    CONSIGNOR = "consignor"
    CONSIGNEE = "consignee"
    END_USER = "end_user"
    DELIVERY_ADDRESS = "delivery_address"
    SIGNATORY = "signatory"
    OTHER = "other"


class Entity(UUIDPrimaryKeyMixin, Base):
    """En part identifisert i en invoice.

    Alle entities screenes mot sanksjonslister (sprint 3). Vi lagrer dem
    separat fra invoice-feltene fordi samme entitet kan opptre i flere
    invoices og fordi vi vil bygge opp en kunnskapsgraf over tid (fase 2).
    """

    __tablename__ = "entities"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType, name="entity_type", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    role: Mapped[EntityRole] = mapped_column(
        Enum(EntityRole, name="entity_role", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    address: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Konfidensscoren LLM ga for denne entiteten (0-1). Lav verdi:
    # verifiser manuelt før sanksjonsscreening-resultater stoles på.
    confidence: Mapped[float | None] = mapped_column(nullable=True)

    invoice: Mapped[Invoice] = relationship(back_populates="entities")
