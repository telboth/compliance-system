"""MVP-modell for utvidet entitetsscreening (nettverksdue-diligence)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._mixins import UUIDPrimaryKeyMixin


class ExtendedScreenRun(UUIDPrimaryKeyMixin, Base):
    """Én kjøring av utvidet screening for én invoice-entitet."""

    __tablename__ = "extended_screen_runs"

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
    aggressiveness: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued", index=True)
    summary_risk: Mapped[str | None] = mapped_column(String(16), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    run_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    invoice = relationship("Invoice")
    entity = relationship("Entity")
    feedback_entries = relationship(
        "ExtendedScreenFeedback",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    sources = relationship(
        "ExtendedScreenSource",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    claims = relationship(
        "ExtendedScreenClaim",
        back_populates="run",
        cascade="all, delete-orphan",
    )
