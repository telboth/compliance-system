"""Tester for bootstrap av sync-status fra statiske seed-flyter."""

from __future__ import annotations

from collections import Counter

import pytest
from sqlalchemy import select

from app.data import export_control_reference as ref
from app.models.export_list_sync import ExportListSyncState
from app.sanctions.embargo import SEED_LIST, seed_db_from_static
from app.services.export_control_service import seed_reference_categories


async def _get_state(db_session, list_code: str) -> ExportListSyncState:
    return (
        await db_session.execute(
            select(ExportListSyncState).where(ExportListSyncState.list_code == list_code)
        )
    ).scalars().one()


@pytest.mark.asyncio
async def test_embargo_seed_bootstraps_sync_state(db_session) -> None:
    inserted = await seed_db_from_static(db_session)
    assert inserted == len(SEED_LIST)

    state = await _get_state(db_session, "EMBG")
    assert state.status == "ok"
    assert state.current_version == "seed"
    assert state.last_checked_at is not None
    assert state.last_imported_at is not None
    assert state.last_imported_by == "seed"
    assert state.item_count == len(SEED_LIST)


@pytest.mark.asyncio
async def test_export_control_seed_bootstraps_sync_state(db_session) -> None:
    created = await seed_reference_categories(db_session)
    await db_session.commit()

    assert created == len(ref.ALL_CATEGORIES)

    counts = Counter(cat.list_code for cat in ref.ALL_CATEGORIES)
    state_i = await _get_state(db_session, "I")
    state_ii = await _get_state(db_session, "II")

    assert state_i.status == "ok"
    assert state_i.current_version == "deksa-seed"
    assert state_i.last_checked_at is not None
    assert state_i.last_imported_at is not None
    assert state_i.last_imported_by == "seed"
    assert state_i.item_count == counts["I"]

    assert state_ii.status == "ok"
    assert state_ii.current_version == "deksa-seed"
    assert state_ii.last_checked_at is not None
    assert state_ii.last_imported_at is not None
    assert state_ii.last_imported_by == "seed"
    assert state_ii.item_count == counts["II"]
