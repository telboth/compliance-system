"""Hjelpere for å logge pipeline-events."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice_pipeline_event import InvoicePipelineEvent


async def append_pipeline_event(
    session: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    stage: str,
    action: str,
    status_from: str | None = None,
    status_to: str | None = None,
    message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> InvoicePipelineEvent:
    """Legg til ett pipeline-event i aktiv transaksjon."""
    row = InvoicePipelineEvent(
        invoice_id=invoice_id,
        stage=stage[:32],
        action=action[:32],
        status_from=(status_from[:32] if status_from else None),
        status_to=(status_to[:32] if status_to else None),
        message=message,
        payload=payload,
    )
    session.add(row)
    await session.flush()
    return row
