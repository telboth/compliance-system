"""Policy Management — compliance-retningslinjer med full versjonshistorikk.

Hver policy har et hode-objekt (CompliancePolicy) og en rekke versjoner
(CompliancePolicyVersion).  Kun én versjon er aktiv om gangen (is_current=True).
Lovhenvisninger lagres som JSONB-liste: [{"law": "EØS-avtalen art. 3", "section": "§ 5"}].
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class CompliancePolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hode-objekt for én compliance-policy (f.eks. «Sanksjonsscreening-prosedyre»).

    Inneholder metadata som er stabile på tvers av versjoner.
    Det faktiske innholdet ligger i CompliancePolicyVersion.
    """

    __tablename__ = "compliance_policies"

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    """Kategori: 'sanctions' | 'export_control' | 'aml' | 'data_privacy' | 'other'"""

    owner: Mapped[str] = mapped_column(String(128), nullable=False)
    """Ansvarlig person eller rolle (f.eks. 'compliance_officer')."""

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    """False → policyen er trukket tilbake og vises ikke i aktiv liste."""

    # Relasjon til versjoner
    versions: Mapped[list[CompliancePolicyVersion]] = relationship(
        back_populates="policy",
        cascade="all, delete-orphan",
        order_by="CompliancePolicyVersion.version_number.desc()",
    )

    __table_args__ = (
        Index("ix_compliance_policies_category", "category"),
        Index("ix_compliance_policies_is_active", "is_active"),
    )


class CompliancePolicyVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Én versjon av en compliance-policy.

    Ny versjon opprettes ved enhver innholdsendring; eksisterende versjoner
    er immutable for sporbarhet.
    """

    __tablename__ = "compliance_policy_versions"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("compliance_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    """Monotont stigende per policy_id, starter på 1."""

    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    """Kun én versjon per policy skal ha is_current=True."""

    content: Mapped[str] = mapped_column(Text, nullable=False)
    """Fulltekst av policyen (Markdown støttes)."""

    change_summary: Mapped[str | None] = mapped_column(String(512), nullable=True)
    """Kort beskrivelse av hva som endret seg fra forrige versjon."""

    # Lovhenvisninger: [{"law": "Forskrift om...", "section": "§ 3 (1)"}]
    law_references: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    effective_from: Mapped[str | None] = mapped_column(String(32), nullable=True)
    """ISO-datostreng (YYYY-MM-DD) for ikrafttredelse, kan settes fremover i tid."""

    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    """Bruker-ID som opprettet denne versjonen."""

    policy: Mapped[CompliancePolicy] = relationship(back_populates="versions")

    __table_args__ = (
        Index("ix_policy_versions_policy_id", "policy_id"),
        Index("ix_policy_versions_is_current", "is_current"),
        Index(
            "uq_policy_versions_policy_version",
            "policy_id",
            "version_number",
            unique=True,
        ),
    )
