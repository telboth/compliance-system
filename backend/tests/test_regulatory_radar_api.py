"""API-tester for Regulatorisk Radar."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.models.regulatory_alert import RegulatoryAlert
from app.services import regulatory_radar_service as rr_svc


def test_parse_ofac_recent_actions_extracts_items() -> None:
    html = (
        '<div class="margin-bottom-4 search-result views-row">'
        '<div><div class="font-sans-lg margin-bottom-05 margin-top-1 text-no-underline">'
        '<a href="/recent-actions/20260618" hreflang="en">Counter Terrorism Designations</a>'
        "</div></div><div><div class=\"margin-top-1 font-sans-2xs line-height-sans-3 margin-bottom-1\">"
        "June 18, 2026 - <a href=\"/recent-actions/sanctions-list-updates\">Sanctions List Updates</a>"
        "</div></div></div>"
    )

    items = rr_svc._parse_ofac_recent_actions(html.encode("utf-8"))

    assert len(items) == 1
    assert items[0]["title"] == "Counter Terrorism Designations"
    assert items[0]["link"] == "https://ofac.treasury.gov/recent-actions/20260618"
    assert items[0]["summary"] == "Sanctions List Updates"
    assert items[0]["guid"] == "https://ofac.treasury.gov/recent-actions/20260618"
    assert items[0]["published_at"] is not None


@pytest.mark.asyncio
async def test_un_feed_uses_browser_headers_and_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = next(row for row in rr_svc.REGULATORY_FEEDS if row["name"] == "UN SC")
    assert source["enabled"] is True

    rss = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>UN SC updates</title>
        <item>
          <title>Update to the consolidated list</title>
          <link>https://main.un.org/securitycouncil/item/1</link>
          <guid>un-item-1</guid>
          <pubDate>Wed, 18 Jun 2026 12:00:00 GMT</pubDate>
          <description>Consolidated list update</description>
        </item>
      </channel>
    </rss>
    """

    class DummySession:
        def __init__(self) -> None:
            self.items: list[object] = []
            self.flushed = False

        def add(self, item: object) -> None:
            self.items.append(item)

        async def flush(self) -> None:
            self.flushed = True

        async def execute(self, *args, **kwargs):
            class _Result:
                def scalars(self):
                    class _Scalars:
                        def all(self):
                            return []

                    return _Scalars()

            return _Result()

    class FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs
            self.calls: list[tuple[str, dict[str, str]]] = []

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str] | None = None):
            self.calls.append((url, headers or {}))
            assert headers is not None
            assert headers["User-Agent"].startswith("Mozilla/5.0")
            assert headers["Accept-Language"] == "en-US,en;q=0.9"
            assert url == source["feed_url"]
            return FakeResponse(rss.encode("utf-8"))

    monkeypatch.setattr(rr_svc.httpx, "AsyncClient", FakeClient)

    session = DummySession()
    result = await rr_svc.fetch_and_store_feed(session, source=source)

    assert result["result_status"] == "imported"
    assert result["new_alerts"] == 1
    assert session.flushed is True
    assert len(session.items) == 1
    assert getattr(session.items[0], "source") == "UN SC"
    assert getattr(session.items[0], "title") == "Update to the consolidated list"


@pytest.mark.asyncio
async def test_fetch_and_store_feed_skips_duplicate_guids_within_same_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = next(row for row in rr_svc.REGULATORY_FEEDS if row["name"] == "UN SC")

    rss = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>UN SC updates</title>
        <item>
          <title>First update</title>
          <link>https://main.un.org/securitycouncil/item/1</link>
          <guid>duplicate-guid</guid>
          <pubDate>Wed, 18 Jun 2026 12:00:00 GMT</pubDate>
          <description>Consolidated list update</description>
        </item>
        <item>
          <title>Second update</title>
          <link>https://main.un.org/securitycouncil/item/2</link>
          <guid>duplicate-guid</guid>
          <pubDate>Wed, 19 Jun 2026 12:00:00 GMT</pubDate>
          <description>Another update with same guid</description>
        </item>
      </channel>
    </rss>
    """

    class DummySession:
        def __init__(self) -> None:
            self.items: list[object] = []
            self.flushed = False

        def add(self, item: object) -> None:
            self.items.append(item)

        async def flush(self) -> None:
            self.flushed = True

        async def execute(self, *args, **kwargs):
            class _Result:
                def scalars(self):
                    class _Scalars:
                        def all(self):
                            return []

                    return _Scalars()

            return _Result()

    class FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str, headers: dict[str, str] | None = None):
            assert url == source["feed_url"]
            return FakeResponse(rss.encode("utf-8"))

    monkeypatch.setattr(rr_svc.httpx, "AsyncClient", FakeClient)

    session = DummySession()
    result = await rr_svc.fetch_and_store_feed(session, source=source)

    assert result["result_status"] == "imported"
    assert result["new_alerts"] == 1
    assert session.flushed is True
    assert len(session.items) == 1
    assert getattr(session.items[0], "guid") == "duplicate-guid"


@pytest.mark.asyncio
async def test_list_sources_includes_status_and_disabled_sources(
    client: AsyncClient,
    db_session,
) -> None:
    alert = RegulatoryAlert(
        source="DEKSA",
        feed_url="https://deksa.no/feed/",
        title="Oppdatering fra DEKSA",
        guid="deksa-test-guid",
        severity="info",
        category="export_control",
        published_at=datetime(2026, 6, 18, tzinfo=UTC),
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
        is_notified=False,
    )
    un_alert = RegulatoryAlert(
        source="UN SC",
        feed_url="https://main.un.org/securitycouncil/feed/1.0/updates_unsc_consolidated_list",
        title="UN update",
        guid="un-test-guid",
        severity="info",
        category="sanctions",
        published_at=datetime(2026, 6, 18, tzinfo=UTC),
        fetched_at=datetime(2026, 6, 18, tzinfo=UTC),
        is_notified=False,
    )
    db_session.add_all([alert, un_alert])
    await db_session.commit()

    response = await client.get("/api/v1/regulatory-radar/sources")
    assert response.status_code == 200, response.text
    body = response.json()
    by_name = {item["name"]: item for item in body}

    assert by_name["DEKSA"]["status"] == "active"
    assert by_name["DEKSA"]["alert_count"] == 1
    assert by_name["OFAC"]["status"] == "empty"
    assert by_name["EUR-Lex"]["status"] == "disabled"
    assert by_name["UN SC"]["status"] == "active"
    assert by_name["UN SC"]["alert_count"] == 1


@pytest.mark.asyncio
async def test_refresh_feeds_returns_per_source_results(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eur_lex_note = (
        "EUR-Lex krever egen RSS-varsling eller brukerkonfigurasjon. "
        "Ingen stabil offentlig feed er satt opp her."
    )

    async def _fake_refresh_sources(*args, **kwargs):
        return [
            {
                "name": "OFAC",
                "feed_url": "https://ofac.treasury.gov/recent-actions/sanctions-list-updates",
                "category": "sanctions",
                "description": "US Office of Foreign Assets Control — sanctions list updates og recent actions",
                "enabled": True,
                "source_type": "html",
                "status_note": "OFACs RSS-feed er avviklet; vi henter recent-actions-siden direkte.",
                "result_status": "checked",
                "new_alerts": 0,
                "message": "Ingen nye varsler.",
            },
            {
                "name": "EUR-Lex",
                "feed_url": "https://eur-lex.europa.eu/content/help/search/predefined-rss.html",
                "category": "export_control",
                "description": "EUR-Lex — sanksjonsrelaterte varsler",
                "enabled": False,
                "source_type": "disabled",
                "status_note": eur_lex_note,
                "result_status": "skipped",
                "new_alerts": 0,
                "message": eur_lex_note,
            },
        ]

    async def _fake_notify(*args, **kwargs) -> int:
        return 0

    monkeypatch.setattr("app.api.v1.regulatory_radar.rr_svc.refresh_sources", _fake_refresh_sources)
    monkeypatch.setattr("app.api.v1.regulatory_radar.rr_svc.notify_unnotified", _fake_notify)

    response = await client.post("/api/v1/regulatory-radar/refresh")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total_new"] == 0
    assert body["new_alerts_by_source"]["OFAC"] == 0
    assert body["sources"][0]["result_status"] == "checked"
    assert body["sources"][1]["result_status"] == "skipped"
