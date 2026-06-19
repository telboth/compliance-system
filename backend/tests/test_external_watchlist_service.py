"""Tester for eksterne watchlist-kilder."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.core.config import get_settings
from app.services.external_watchlist_service import (
    SOURCE_UK_SANCTIONS,
    SOURCE_WORLD_BANK_DEBARRED,
    _extract_world_bank_api_details,
    ingest_external_watchlists,
    list_external_source_health,
)


def test_extract_world_bank_api_details_from_public_html() -> None:
    html = """
    <script>
      var prodtabApi = "https://example.test/api";
      var propApiKey = "public-key";
    </script>
    """

    api_url, api_key = _extract_world_bank_api_details(html)

    assert api_url == "https://example.test/api"
    assert api_key == "public-key"


@pytest.mark.asyncio
async def test_world_bank_ingest_uses_public_page_scrape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page_html = """
    <script>
      var prodtabApi = "https://example.test/api";
      var propApiKey = "public-key";
    </script>
    """
    payload = {
        "response": {
            "ZPROCSUPP": [
                {
                    "SUPP_ID": "WB-1",
                    "SUPP_NAME": "Acme Debarred Ltd",
                    "COUNTRY_NAME": "Norway",
                    "DEBAR_TYPE": "Debarred",
                    "DEBAR_FROM_DATE": "2024-01-01",
                    "DEBAR_TO_DATE": "2025-01-01",
                    "DEBAR_REASON": "Test reason",
                }
            ]
        }
    }

    class DummySession:
        async def commit(self) -> None:
            return None

    class DummyStatus:
        def __init__(self) -> None:
            self.update_status = "unknown"
            self.error_message = None
            self.last_updated = None
            self.entry_count = None

    class FakeResponse:
        def __init__(self, *, text: str = "", json_data: dict | None = None) -> None:
            self.text = text
            self._json_data = json_data

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            assert self._json_data is not None
            return self._json_data

    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, str] | None]] = []

        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str] | None = None):
            self.calls.append((url, headers))
            if "worldbank.org/en/projects-operations/procurement/debarred-firms" in url:
                return FakeResponse(text=page_html)
            if url == "https://example.test/api":
                assert headers == {"apikey": "public-key"}
                return FakeResponse(json_data=payload)
            raise AssertionError(f"Unexpected URL: {url}")

    fake_client = FakeClient()
    captured_rows: dict[str, list[dict[str, object]]] = {}

    async def _fake_get_or_create_status_row(session, source: str):
        return DummyStatus()

    async def _fake_store_entries(session, *, source: str, rows: list[dict[str, object]]) -> None:
        captured_rows[source] = rows

    monkeypatch.setattr(
        "app.services.external_watchlist_service._get_or_create_status_row",
        _fake_get_or_create_status_row,
    )
    monkeypatch.setattr("app.services.external_watchlist_service._store_entries", _fake_store_entries)
    monkeypatch.setattr("app.services.external_watchlist_service.httpx.AsyncClient", lambda **kwargs: fake_client)

    result = await ingest_external_watchlists(DummySession(), sources=[SOURCE_WORLD_BANK_DEBARRED])

    assert result == [
        {
            "source": SOURCE_WORLD_BANK_DEBARRED,
            "status": "success",
            "entry_count": 1,
        }
    ]
    assert SOURCE_WORLD_BANK_DEBARRED in captured_rows
    assert captured_rows[SOURCE_WORLD_BANK_DEBARRED][0]["external_id"] == "WB-1"
    assert captured_rows[SOURCE_WORLD_BANK_DEBARRED][0]["name"] == "Acme Debarred Ltd"
    assert [url for url, _ in fake_client.calls] == [
        "https://www.worldbank.org/en/projects-operations/procurement/debarred-firms",
        "https://example.test/api",
    ]


@pytest.mark.asyncio
async def test_external_source_health_uses_source_specific_stale_thresholds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime.now(UTC)
    rows = [
        SimpleNamespace(
            source=SOURCE_UK_SANCTIONS,
            last_updated=now - timedelta(hours=48),
            entry_count=10,
            update_status="success",
            error_message=None,
        ),
        SimpleNamespace(
            source=SOURCE_WORLD_BANK_DEBARRED,
            last_updated=now - timedelta(days=10),
            entry_count=20,
            update_status="success",
            error_message=None,
        ),
    ]

    class FakeScalarResult:
        def all(self) -> list[SimpleNamespace]:
            return rows

    class FakeExecuteResult:
        def scalars(self) -> FakeScalarResult:
            return FakeScalarResult()

    class FakeSession:
        async def execute(self, *args, **kwargs) -> FakeExecuteResult:
            return FakeExecuteResult()

    settings = get_settings()
    monkeypatch.setattr(settings, "external_source_stale_hours", 36)
    monkeypatch.setattr(settings, "world_bank_debarred_stale_days", 45)

    health_rows = await list_external_source_health(FakeSession(), include_brreg_probe=False)
    health = {str(row["source"]): row for row in health_rows if isinstance(row, dict)}

    assert health[SOURCE_UK_SANCTIONS]["stale"] is True
    assert health[SOURCE_WORLD_BANK_DEBARRED]["stale"] is False
