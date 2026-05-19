"""Persistens av frontend-preferanser for invoice-listen."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_preference import UserPreference
from app.schemas.invoice import InvoiceListPreferencesUpdate


INVOICE_LIST_PREF_KEY = "invoice_list"


async def get_invoice_list_preferences(
    session: AsyncSession,
    *,
    actor_name: str,
) -> tuple[dict, datetime | None]:
    row = (
        await session.execute(
            select(UserPreference).where(
                UserPreference.actor_name == actor_name,
                UserPreference.preference_key == INVOICE_LIST_PREF_KEY,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return {
            "table_col_widths": {},
            "table_col_presets": [],
            "default_filters": {},
        }, None
    value = row.value if isinstance(row.value, dict) else {}
    return {
        "table_col_widths": value.get("table_col_widths") or {},
        "table_col_presets": value.get("table_col_presets") or [],
        "default_filters": value.get("default_filters") or {},
    }, row.updated_at


async def update_invoice_list_preferences(
    session: AsyncSession,
    *,
    actor_name: str,
    update: InvoiceListPreferencesUpdate,
) -> tuple[dict, datetime | None]:
    row = (
        await session.execute(
            select(UserPreference).where(
                UserPreference.actor_name == actor_name,
                UserPreference.preference_key == INVOICE_LIST_PREF_KEY,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = UserPreference(
            actor_name=actor_name,
            preference_key=INVOICE_LIST_PREF_KEY,
            value={},
        )
        session.add(row)
        await session.flush()

    current = row.value if isinstance(row.value, dict) else {}
    payload = {
        "table_col_widths": current.get("table_col_widths") or {},
        "table_col_presets": current.get("table_col_presets") or [],
        "default_filters": current.get("default_filters") or {},
    }
    data = update.model_dump(exclude_unset=True)
    for key in ("table_col_widths", "table_col_presets", "default_filters"):
        if key in data and data[key] is not None:
            payload[key] = data[key]
    row.value = payload
    await session.commit()
    await session.refresh(row)
    return payload, row.updated_at
