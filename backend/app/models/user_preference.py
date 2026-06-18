"""Persisted brukerpreferanser (UI-oppsett per bruker)."""

from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._mixins import TimestampMixin, UUIDPrimaryKeyMixin


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Key/value-preferanser per bruker for frontend-oppsett."""

    __tablename__ = "user_preferences"
    __table_args__ = (UniqueConstraint("actor_name", "preference_key", name="uq_user_preferences_actor_key"),)

    actor_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    preference_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
