"""Regulatorisk Radar — henter og lagrer regulatoriske oppdateringer fra flere kilder.

Støttede kilder:
  - OFAC (US Treasury) — recent actions / sanctions list updates
  - HM Treasury (OFSI) — britiske sanksjonsoppdateringer
  - EUR-Lex — manuell RSS-varsling / ingen stabil offentlig feed
  - UN Security Council — offisiell RSS-feed
  - DEKSA — eksportkontrolloppdateringer

Bruker stdlib xml.etree.ElementTree + httpx for ingen ekstra avhengigheter.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, TypedDict
from urllib.parse import urljoin

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory_alert import RegulatoryAlert
from app.services import notification_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Definisjon av kilder
# ---------------------------------------------------------------------------


class RegulatorySourceConfig(TypedDict):
    name: str
    feed_url: str
    category: str
    description: str
    enabled: bool
    source_type: str
    status_note: str | None
    headers: dict[str, str] | None


class RegulatorySourceStatus(TypedDict):
    name: str
    feed_url: str
    category: str
    description: str
    enabled: bool
    source_type: str
    status_note: str | None
    status: str
    alert_count: int
    latest_alert_at: datetime | None


class RegulatoryRefreshSourceResult(TypedDict):
    name: str
    feed_url: str
    category: str
    description: str
    enabled: bool
    source_type: str
    status_note: str | None
    result_status: str
    new_alerts: int
    message: str | None


_DEFAULT_FEED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/atom+xml, text/xml, text/html, application/xhtml+xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


REGULATORY_FEEDS: list[RegulatorySourceConfig] = [
    {
        "name": "OFAC",
        "feed_url": "https://ofac.treasury.gov/recent-actions/sanctions-list-updates",
        "category": "sanctions",
        "description": "US Office of Foreign Assets Control — sanctions list updates og recent actions",
        "enabled": True,
        "source_type": "html",
        "status_note": "OFACs RSS-feed er avviklet; vi henter recent-actions-siden direkte.",
        "headers": None,
    },
    {
        "name": "EUR-Lex",
        "feed_url": "https://eur-lex.europa.eu/content/help/search/predefined-rss.html",
        "category": "export_control",
        "description": "EUR-Lex — sanksjonsrelaterte varsler",
        "enabled": False,
        "source_type": "disabled",
        "status_note": (
            "EUR-Lex krever egen RSS-varsling eller brukerkonfigurasjon. "
            "Ingen stabil offentlig feed er satt opp her."
        ),
        "headers": None,
    },
    {
        "name": "HM Treasury",
        "feed_url": "https://ofsi.blog.gov.uk/feed/",
        "category": "sanctions",
        "description": "UK HM Treasury / OFSI — blogg og sanksjonsoppdateringer",
        "enabled": True,
        "source_type": "atom",
        "status_note": "OFSI-bloggen brukes som aktiv oppdateringskilde for britiske sanksjonsendringer.",
        "headers": None,
    },
    {
        "name": "UN SC",
        "feed_url": "https://main.un.org/securitycouncil/feed/1.0/updates_unsc_consolidated_list",
        "category": "sanctions",
        "description": "FNs sikkerhetsråd — konsolidert sanksjonsliste",
        "enabled": True,
        "source_type": "rss",
        "status_note": "Offisiell RSS-feed som hentes automatisk.",
        "headers": None,
    },
    {
        "name": "DEKSA",
        "feed_url": "https://deksa.no/feed/",
        "category": "export_control",
        "description": "Direktoratet for eksportkontroll og sanksjoner — norske "
        "listeoppdateringer, sanksjonsendringer og varslinger",
        "enabled": True,
        "source_type": "rss",
        "status_note": "Offisiell DEKSA-feed.",
        "headers": None,
    },
]

# Nøkkelord som setter severity til "critical".
# Inkluderer norske termer for DEKSA-feeden (som er på bokmål).
_CRITICAL_KEYWORDS = frozenset(
    {
        # Engelsk
        "added",
        "listed",
        "designated",
        "sanctioned",
        "blocked",
        "consolidated",
        "update",
        "amendment",
        # Norsk
        "sanksjon",
        "embargo",
        "eksportforbud",
        "listeført",
        "tiltak mot",
    }
)

# XML-namespacer brukt i Atom-feeds
_ATOM_NS = "http://www.w3.org/2005/Atom"


# ---------------------------------------------------------------------------
# Intern hjelp
# ---------------------------------------------------------------------------


def _guess_severity(title: str, summary: str | None) -> str:
    text = (title + " " + (summary or "")).lower()
    if any(kw in text for kw in _CRITICAL_KEYWORDS):
        return "critical"
    return "info"


def _parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            dt = datetime.strptime(raw, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(raw)
    except Exception:
        return None


def _parse_ofac_recent_actions(content: bytes) -> list[dict[str, Any]]:
    """Trekk ut OFAC recent-actions fra HTML-listesiden."""
    text = content.decode("utf-8", errors="ignore")
    items: list[dict[str, Any]] = []
    pattern = re.compile(
        r'<div class="margin-bottom-4 search-result views-row">.*?'
        r'<a href="(?P<link>/recent-actions/[^"]+)" hreflang="en">(?P<title>.*?)</a>.*?'
        r'(?P<date>[A-Za-z]+ \d{1,2}, \d{4}) -\s*<a href="[^"]+">(?P<category>.*?)</a>',
        re.S,
    )
    for match in pattern.finditer(text):
        title = unescape(match.group("title")).strip()
        link = urljoin("https://ofac.treasury.gov", match.group("link"))
        category = unescape(re.sub(r"<[^>]+>", "", match.group("category"))).strip() or None
        published_at = _parse_date(match.group("date"))
        if title:
            items.append(
                {
                    "title": title[:512],
                    "link": link,
                    "summary": category,
                    "guid": link[:1024],
                    "published_at": published_at,
                }
            )
    return items


def _parse_rss(content: bytes) -> list[dict[str, Any]]:
    """Trekk ut items fra RSS 2.0-format."""
    root = ET.fromstring(content)  # noqa: S314
    items: list[dict[str, Any]] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip() or None
        summary = (item.findtext("description") or "").strip() or None
        guid = (item.findtext("guid") or link or title).strip()
        pub_raw = item.findtext("pubDate")
        published_at = _parse_date(pub_raw)
        if title:
            items.append(
                {
                    "title": title[:512],
                    "link": link,
                    "summary": summary,
                    "guid": guid[:1024],
                    "published_at": published_at,
                }
            )
    return items


def _parse_atom(content: bytes) -> list[dict[str, Any]]:
    """Trekk ut entries fra Atom-format."""
    root = ET.fromstring(content)  # noqa: S314
    items: list[dict[str, Any]] = []
    ns = {"a": _ATOM_NS}
    for entry in root.findall("a:entry", ns):
        title_el = entry.find("a:title", ns)
        title = (title_el.text or "").strip() if title_el is not None else ""
        link_el = entry.find("a:link", ns)
        link = (link_el.get("href") or "").strip() if link_el is not None else None
        summary_el = entry.find("a:summary", ns) or entry.find("a:content", ns)
        summary = (summary_el.text or "").strip() if summary_el is not None else None
        id_el = entry.find("a:id", ns)
        guid = ((id_el.text or link or title) or "").strip()
        updated_el = entry.find("a:updated", ns) or entry.find("a:published", ns)
        published_at = _parse_date(updated_el.text if updated_el is not None else None)
        if title:
            items.append(
                {
                    "title": title[:512],
                    "link": link,
                    "summary": summary,
                    "guid": guid[:1024],
                    "published_at": published_at,
                }
            )
    return items


def _parse_feed(content: bytes) -> list[dict[str, Any]]:
    """Prøv RSS, fall tilbake til Atom."""
    try:
        root = ET.fromstring(content)  # noqa: S314
    except ET.ParseError as exc:
        logger.warning("XML-parsefeil: %s", exc)
        return []

    tag = root.tag.lower()
    if "rss" in tag or root.find("channel") is not None:
        return _parse_rss(content)
    if "feed" in tag or _ATOM_NS in tag:
        return _parse_atom(content)
    # Prøv begge
    items = _parse_rss(content)
    return items or _parse_atom(content)


# ---------------------------------------------------------------------------
# Offentlig API
# ---------------------------------------------------------------------------


async def fetch_and_store_feed(
    session: AsyncSession,
    *,
    source: RegulatorySourceConfig,
    timeout_seconds: int = 30,
) -> RegulatoryRefreshSourceResult:
    """Hent én kilde og lagre nye elementer i DB."""
    base_result: RegulatoryRefreshSourceResult = {
        "name": source["name"],
        "feed_url": source["feed_url"],
        "category": source["category"],
        "description": source["description"],
        "enabled": source["enabled"],
        "source_type": source["source_type"],
        "status_note": source["status_note"],
        "result_status": "checked",
        "new_alerts": 0,
        "message": None,
    }

    if not source["enabled"]:
        message = source["status_note"] or "Kilden er deaktivert."
        logger.info("Kilde %s er deaktivert: %s", source["name"], message)
        base_result["result_status"] = "skipped"
        base_result["message"] = message
        return base_result

    try:
        request_headers = dict(_DEFAULT_FEED_HEADERS)
        if source.get("headers"):
            request_headers.update(source["headers"])
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = await client.get(
                source["feed_url"],
                headers=request_headers,
            )
            resp.raise_for_status()
            content = resp.content
    except Exception as exc:
        logger.error("Feil ved henting av feed %s (%s): %s", source["name"], source["feed_url"], exc)
        base_result["result_status"] = "error"
        base_result["message"] = str(exc)[:512]
        return base_result

    if source["source_type"] == "html":
        parsed = _parse_ofac_recent_actions(content)
    else:
        parsed = _parse_feed(content)

    if not parsed:
        logger.info("Ingen elementer funnet i feed %s", source["name"])
        base_result["result_status"] = "checked"
        base_result["message"] = "Ingen elementer funnet i kilden."
        return base_result

    # Hent eksisterende guids og hold styr på hva vi allerede har akseptert i denne kjøringen.
    guids = [item["guid"] for item in parsed]
    existing_guids: set[str] = set(
        (await session.execute(select(RegulatoryAlert.guid).where(RegulatoryAlert.guid.in_(guids)))).scalars().all()
    )
    seen_guids = set(existing_guids)
    new_count = 0
    for item in parsed:
        guid = (item["guid"] or "").strip()
        if not guid or guid in seen_guids:
            continue
        seen_guids.add(guid)
        severity = _guess_severity(item["title"], item.get("summary"))
        alert = RegulatoryAlert(
            source=source["name"],
            feed_url=source["feed_url"],
            title=item["title"],
            link=item.get("link"),
            summary=item.get("summary"),
            published_at=item.get("published_at"),
            fetched_at=datetime.now(UTC),
            guid=guid,
            severity=severity,
            category=source["category"],
            is_notified=False,
        )
        session.add(alert)
        new_count += 1

    if new_count:
        await session.flush()
        logger.info("Feed %s: %d nye varsler lagret", source["name"], new_count)

    base_result["result_status"] = "imported" if new_count else "checked"
    base_result["new_alerts"] = new_count
    base_result["message"] = f"{new_count} nye varsler lagret" if new_count else "Ingen nye varsler."
    return base_result


async def _load_source_stats(session: AsyncSession) -> dict[str, dict[str, Any]]:
    stmt = select(
        RegulatoryAlert.source,
        func.count().label("alert_count"),
        func.max(func.coalesce(RegulatoryAlert.published_at, RegulatoryAlert.fetched_at)).label("latest_alert_at"),
    ).group_by(RegulatoryAlert.source)
    rows = (await session.execute(stmt)).all()
    return {
        source: {
            "alert_count": int(alert_count),
            "latest_alert_at": latest_alert_at,
        }
        for source, alert_count, latest_alert_at in rows
    }


async def list_sources(session: AsyncSession) -> list[RegulatorySourceStatus]:
    """Returner konfigurerte kilder med enkle statusdata fra lagrede varsler."""
    stats = await _load_source_stats(session)
    sources: list[RegulatorySourceStatus] = []
    for source in REGULATORY_FEEDS:
        data = stats.get(source["name"])
        alert_count = data["alert_count"] if data else 0
        latest_alert_at = data["latest_alert_at"] if data else None
        status = "disabled" if not source["enabled"] else ("active" if alert_count else "empty")
        sources.append(
            {
                "name": source["name"],
                "feed_url": source["feed_url"],
                "category": source["category"],
                "description": source["description"],
                "enabled": source["enabled"],
                "source_type": source["source_type"],
                "status_note": source["status_note"],
                "status": status,
                "alert_count": alert_count,
                "latest_alert_at": latest_alert_at,
            }
        )
    return sources


async def refresh_sources(session: AsyncSession, *, timeout_seconds: int = 30) -> list[RegulatoryRefreshSourceResult]:
    """Kjør alle konfigurerte kilder og returner detaljer per kilde."""
    results: list[RegulatoryRefreshSourceResult] = []
    for source in REGULATORY_FEEDS:
        result = await fetch_and_store_feed(session, source=source, timeout_seconds=timeout_seconds)
        results.append(result)
    return results


async def run_all_feeds(session: AsyncSession, *, timeout_seconds: int = 30) -> dict[str, int]:
    """Kjør alle konfigurerte kilder og returner {source: antall_nye}."""
    results = await refresh_sources(session, timeout_seconds=timeout_seconds)
    return {result["name"]: result["new_alerts"] for result in results}


async def notify_unnotified(session: AsyncSession) -> int:
    """Send in-app-varsel for alle varsler som ennå ikke er varslet. Returnerer antall."""
    stmt = select(RegulatoryAlert).where(RegulatoryAlert.is_notified.is_(False))
    rows = list((await session.execute(stmt)).scalars().all())
    count = 0
    for alert in rows:
        label = "[KRITISK]" if alert.severity == "critical" else "[Info]"
        level = "error" if alert.severity == "critical" else "info"
        await notification_service.create(
            session,
            message=f"{label} {alert.source}: {alert.title}"[:512],
            level=level,
            target_roles=["compliance_officer", "admin"],
        )
        alert.is_notified = True
        count += 1
    if count:
        await session.flush()
    return count


async def list_alerts(
    session: AsyncSession,
    *,
    source: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RegulatoryAlert], int]:
    """Returner (varsler, total)."""
    base = select(RegulatoryAlert)
    if source:
        base = base.where(RegulatoryAlert.source == source)
    if severity:
        base = base.where(RegulatoryAlert.severity == severity)

    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    rows = list(
        (
            await session.execute(
                base.order_by(
                    RegulatoryAlert.published_at.desc().nulls_last(),
                    RegulatoryAlert.fetched_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return rows, total
