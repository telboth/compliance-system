"""Rule og RuleVersion — versjonert YAML-regelmotor.

En Rule er en navngitt, versjonert compliance-regel. Hvert gang regelen
endres lages en ny RuleVersion — den forrige beholdes for audit-spor.
Rules evalueres mot InvoiceContext (se rule_engine_service.py).

YAML-format (lagres i rule_definition):
  name: Russland-embargo
  description: Blokkér alle forsendelser til Russland eller Hviterussland
  severity: red          # green | yellow | red
  conditions:
    operator: OR
    rules:
      - field: destination_country
        op: in
        value: [RU, BY]
      - field: entities.country
        op: in
        value: [RU, BY]

Støttede op-verdier:
  eq, neq, in, not_in, contains, not_contains, regex, gt, gte, lt, lte, exists
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class RuleSeverity(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class Rule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """En navngitt compliance-regel med aktiv versjonspeker."""

    __tablename__ = "rules"

    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[RuleSeverity] = mapped_column(
        Enum(RuleSeverity, name="rule_severity", values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=RuleSeverity.YELLOW,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    # Peker til aktiv versjon — oppdateres ved endring
    active_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    versions: Mapped[list[RuleVersion]] = relationship(
        back_populates="rule", cascade="all, delete-orphan", order_by="RuleVersion.version"
    )


class RuleVersion(UUIDPrimaryKeyMixin, Base):
    """Én spesifikk versjon av en regel (immutable etter opprettelse).

    Ingen updated_at — versjoner skal aldri endres.
    """

    __tablename__ = "rule_versions"

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # YAML-tekst slik brukeren skrev det
    rule_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    # Parsed JSON-representasjon (caches parse-steget)
    rule_definition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Hvem opprettet versjonen
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    comment: Mapped[str | None] = mapped_column(String(512), nullable=True)

    rule: Mapped[Rule] = relationship(back_populates="versions")
