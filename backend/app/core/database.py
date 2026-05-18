"""
Asynkron SQLAlchemy-oppsett.

Vi bruker SQLAlchemy 2.0 med asyncpg-driver. Modeller arver fra `Base`.
Bruk `get_session` som FastAPI-dependency for å få en session per request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

# Konsistent navngivning på constraints og indekser gjør Alembic-migrasjoner
# stabile på tvers av databaser og hjelper ved feilsøking i produksjon.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Felles base for alle SQLAlchemy-modeller."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _create_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.app_debug,
        pool_pre_ping=True,
        future=True,
    )


_engine: AsyncEngine = _create_engine()
_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-dependency som gir en async database-session per request."""
    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]
"""Type-alias for inj. av session i endepunkter: `session: SessionDep`."""


def get_engine() -> AsyncEngine:
    """Eksponert for bruk i Alembic og tester."""
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Eksponert for bakgrunnsoppgaver som trenger en ny sesjon utenfor request-syklusen."""
    return _session_factory
