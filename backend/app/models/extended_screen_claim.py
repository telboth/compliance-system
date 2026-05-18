"""Persisted claims/evidens for utvidet screening."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import UUIDPrimaryKeyMixin


class ExtendedScreenClaim(UUIDPrimaryKeyMixin, Base):
    """Én strukturert claim med evidens for en utvidet-screening-run."""

    __tablename__ = "extended_screen_claims"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("extended_screen_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    claim_subject: Mapped[str] = mapped_column(String(512), nullable=False)
    claim_object: Mapped[str] = mapped_column(String(1024), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    verification_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="unverified",
    )
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    quoted_text: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    run = relationship("ExtendedScreenRun", back_populates="claims")
    invoice = relationship("Invoice")
    entity = relationship("Entity")
