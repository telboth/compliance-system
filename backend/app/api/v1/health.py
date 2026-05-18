"""Helsesjekk-endepunkt."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.database import SessionDep

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
async def health(session: SessionDep) -> HealthResponse:
    """Sjekker at API-et og databasen er tilgjengelig."""
    try:
        await session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "unavailable"

    return HealthResponse(status="ok", database=db_status)
