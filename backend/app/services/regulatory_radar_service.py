"""Regulatorisk Radar — henter og lagrer RSS/Atom-feeds fra regulatoriske kilder.

Støttede kilder:
  - OFAC (US Treasury) — sanctions updates
  - EUR-Lex — EU forordninger og direktiver
  - HM Treasury (UK) — UK sanctions
  - UN Security Council — consolidated list updates

Bruker stdlib xml.etree.ElementTree + httpx for ingen ekstra avhengigheter.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory_alert import RegulatoryAlert
from app.services import notification_service

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Definisjon av feeds
# ---------------------------------------------------------------------------

REGULATORY_FEEDS: list[dict[str, str]] = [
    {
        "name": "OFAC",
        "feed_url": "https://ofac.treasury.gov/media/rss/recent-actions.xml",
        "category": "sanctions",
        "description": "US Office of Foreign Assets Control — nyeste sanksjonsbeslutninger",
    },
    {
        "name": "EUR-Lex",
        "feed_url": "https://eur-lex.europa.eu/rss/atom/EU_Notices_OJL_L.xml",
        "category": "export_control",
        "description": "EU Official Journal — forordninger og direktiver (L-serien)",
    },
    {
        "name": "HM Treasury",
        "feed_url": "https://www.gov.uk/government/collections/financial-sanctions-regime-specific-consolidated-lists.atom",
        "category": "sanctions",
        "description": "UK HM Treasury — Financial Sanctions konsolidert liste",
    },
    {
        "name": "UN SC",
        "feed_url": "https://www.un.org/sc/suborg/en/sanctions/un-sc-consolidated-list.xml",
        "category": "sanctions",
        "description": "FNs sikkerhetsråd — konsolidert sanksjonsliste",
    },
    {
        "name": "DEKSA",
        "feed_url": "https://deksa.no/feed/",
        "category": "export_control",
        "description": "Direktoratet for eksportkontroll og sanksjoner — norske "
        "listeoppdateringer, sanksjonsendringer og varslinger",
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
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
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
    name: str,
    feed_url: str,
    category: str,
    timeout_seconds: int = 30,
) -> int:
    """Hent ett feed og lagre nye elementer i DB. Returnerer antall nye rader."""
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = await client.get(feed_url, headers={"Accept": "application/rss+xml, application/atom+xml, text/xml"})
            resp.raise_for_status()
            content = resp.content
    except Exception as exc:
        logger.error("Feil ved henting av feed %s (%s): %s", name, feed_url, exc)
        return 0

    parsed = _parse_feed(content)
    if not parsed:
        logger.info("Ingen elementer funnet i feed %s", name)
        return 0

    # Hent eksisterende guids for å unngå duplikater
    guids = [item["guid"] for item in parsed]
    existing_guids: set[str] = set(
        (await session.execute(select(RegulatoryAlert.guid).where(RegulatoryAlert.guid.in_(guids)))).scalars().all()
    )

    new_count = 0
    for item in parsed:
        if item["guid"] in existing_guids:
            continue
        severity = _guess_severity(item["title"], item.get("summary"))
        alert = RegulatoryAlert(
            source=name,
            feed_url=feed_url,
            title=item["title"],
            link=item.get("link"),
            summary=item.get("summary"),
            published_at=item.get("published_at"),
            fetched_at=datetime.now(UTC),
            guid=item["guid"],
            severity=severity,
            category=category,
            is_notified=False,
        )
        session.add(alert)
        new_count += 1

    if new_count:
        await session.flush()
        logger.info("Feed %s: %d nye varsler lagret", name, new_count)

    return new_count


async def run_all_feeds(session: AsyncSession, *, timeout_seconds: int = 30) -> dict[str, int]:
    """Kjør alle konfigurerte feeds og returner {source: antall_nye}."""
    results: dict[str, int] = {}
    for feed in REGULATORY_FEEDS:
        count = await fetch_and_store_feed(
            session,
            name=feed["name"],
            feed_url=feed["feed_url"],
            category=feed["category"],
            timeout_seconds=timeout_seconds,
        )
        results[feed["name"]] = count
    return results


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
