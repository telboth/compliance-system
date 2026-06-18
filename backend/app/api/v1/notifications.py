"""Notifications-API — in-app varsler."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.database import SessionDep
from app.services import notification_service

router = APIRouter()


class NotificationOut(BaseModel):
    id: uuid.UUID
    message: str
    level: str
    invoice_id: uuid.UUID | None
    target_roles: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="Hent varsler for en brukerrolle",
)
async def list_notifications(
    session: SessionDep,
    role: str = Query(..., description="Brukerens rolle, f.eks. 'compliance_officer'"),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> NotificationListResponse:
    """Returnerer varsler sendt til den angitte rollen, nyeste først.

    Frontend sender gjeldende rolle fra AuthContext.
    """
    items, total = await notification_service.list_for_role(session, role=role, limit=limit, offset=offset)
    return NotificationListResponse(
        items=[NotificationOut.model_validate(n) for n in items],
        total=total,
    )
