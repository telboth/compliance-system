"""Bygg kartdata for forsendelser (avsender -> mottaker)."""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dtime
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.entity import Entity, EntityRole
from app.models.geocode_cache import GeocodeCache
from app.models.invoice import ComplianceScore, Invoice
from app.models.screening import MatchStatus, ScreeningResult
from app.schemas.shipment_map import ShipmentMapPoint, ShipmentMapResponse, ShipmentMapRoute

logger = get_logger(__name__)

_FAILED_CACHE_TTL = timedelta(days=7)
_CITY_WORD_RE = re.compile(r"[A-Za-z][A-Za-z\s.-]{1,80}")
_NUMERIC_TOKEN_RE = re.compile(r"^\d+$")


@dataclass(slots=True)
class _Location:
    name: str | None
    country: str | None
    address: str | None
    city_hint: str | None


@dataclass(slots=True)
class _GeocodeResult:
    lat: float
    lon: float
    precision: str
    cache_hit: bool


class _GeocodeBudget:
    def __init__(self, max_external_calls: int) -> None:
        self.max_external_calls = max(0, max_external_calls)
        self.external_calls = 0
        self.cache_hits = 0
        self._last_external_call = 0.0

    async def throttle(self) -> None:
        # Nominatim usage policy: maks ~1 req/s pa offentlig instans.
        now = time.monotonic()
        elapsed = now - self._last_external_call
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        self._last_external_call = time.monotonic()

    def can_call_external(self) -> bool:
        return self.external_calls < self.max_external_calls


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    v = " ".join(value.split()).strip()
    return v or None


def _clean_country(country: str | None) -> str | None:
    value = _clean_text(country)
    if not value:
        return None
    letters = "".join(ch for ch in value.upper() if ch.isalpha())
    return letters[:2] if letters else None


def _cache_key(*, query: str, country: str | None, precision: str) -> str:
    return f"nominatim|{precision}|{(country or '').upper()}|{query.lower()}"


def _extract_city_candidates(address: str | None) -> list[str]:
    if not address:
        return []
    parts = [p.strip() for p in re.split(r"[,;/]", address) if p.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for part in reversed(parts):
        part = re.sub(r"\b\d{3,6}\b", " ", part).strip()
        if not part or _NUMERIC_TOKEN_RE.match(part):
            continue
        if not _CITY_WORD_RE.search(part):
            continue
        normalized = part.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        out.append(part)
        if len(out) >= 3:
            break
    return out


def _location_queries(loc: _Location) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    country = _clean_country(loc.country)
    address = _clean_text(loc.address)
    city_hint = _clean_text(loc.city_hint)

    if address and country:
        queries.append((f"{address}, {country}", "address"))
        for city in _extract_city_candidates(address):
            queries.append((f"{city}, {country}", "city"))
    if city_hint and country:
        queries.append((f"{city_hint}, {country}", "city"))
    if country:
        # q=ISO2 + countrycodes fungerer stabilt for landsentrum.
        queries.append((country, "country"))

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for query, precision in queries:
        key = (query.lower(), precision)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((query, precision))
    return deduped


async def _read_cache(
    session: AsyncSession,
    *,
    cache_key_value: str,
) -> GeocodeCache | None:
    row = (
        await session.execute(select(GeocodeCache).where(GeocodeCache.cache_key == cache_key_value))
    ).scalar_one_or_none()
    return row


async def _nominatim_geocode(
    *,
    query: str,
    country: str | None,
) -> tuple[float, float] | None:
    settings = get_settings()
    params = {
        "format": "jsonv2",
        "limit": 1,
        "q": query,
    }
    if country:
        params["countrycodes"] = country.lower()
    headers = {
        "User-Agent": settings.geocode_user_agent,
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=max(4, settings.geocode_timeout_seconds)) as client:
        response = await client.get(settings.geocode_nominatim_url, params=params, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f"Nominatim HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, list) or not payload:
        return None
    row = payload[0]
    lat_raw = row.get("lat")
    lon_raw = row.get("lon")
    if lat_raw is None or lon_raw is None:
        return None
    return float(lat_raw), float(lon_raw)


async def _geocode_location(
    session: AsyncSession,
    *,
    loc: _Location,
    budget: _GeocodeBudget,
) -> _GeocodeResult | None:
    country = _clean_country(loc.country)
    for query, precision in _location_queries(loc):
        key = _cache_key(query=query, country=country, precision=precision)
        cached = await _read_cache(session, cache_key_value=key)
        if cached is not None:
            cached.hit_count = int(cached.hit_count or 0) + 1
            cached.last_used_at = datetime.now(UTC)
            budget.cache_hits += 1
            if cached.status == "success" and cached.latitude is not None and cached.longitude is not None:
                return _GeocodeResult(
                    lat=float(cached.latitude),
                    lon=float(cached.longitude),
                    precision=cached.precision_level,
                    cache_hit=True,
                )
            if cached.status == "failed" and cached.updated_at >= datetime.now(UTC) - _FAILED_CACHE_TTL:
                continue

        if not budget.can_call_external():
            continue

        await budget.throttle()
        budget.external_calls += 1
        try:
            hit = await _nominatim_geocode(query=query, country=country)
        except Exception as exc:
            logger.warning("shipment_map_geocode_failed", query=query, error=str(exc))
            if cached is None:
                session.add(
                    GeocodeCache(
                        cache_key=key,
                        provider="nominatim",
                        query_text=query,
                        country_code=country,
                        precision_level=precision,
                        status="failed",
                        error_message=str(exc)[:500],
                        last_used_at=datetime.now(UTC),
                    )
                )
            else:
                cached.status = "failed"
                cached.error_message = str(exc)[:500]
                cached.last_used_at = datetime.now(UTC)
            continue

        if hit is None:
            if cached is None:
                session.add(
                    GeocodeCache(
                        cache_key=key,
                        provider="nominatim",
                        query_text=query,
                        country_code=country,
                        precision_level=precision,
                        status="failed",
                        error_message="No result",
                        last_used_at=datetime.now(UTC),
                    )
                )
            else:
                cached.status = "failed"
                cached.error_message = "No result"
                cached.last_used_at = datetime.now(UTC)
            continue

        lat, lon = hit
        if cached is None:
            session.add(
                GeocodeCache(
                    cache_key=key,
                    provider="nominatim",
                    query_text=query,
                    country_code=country,
                    precision_level=precision,
                    status="success",
                    latitude=lat,
                    longitude=lon,
                    hit_count=1,
                    last_used_at=datetime.now(UTC),
                )
            )
        else:
            cached.status = "success"
            cached.latitude = lat
            cached.longitude = lon
            cached.error_message = None
            cached.precision_level = precision
            cached.last_used_at = datetime.now(UTC)
            cached.hit_count = int(cached.hit_count or 0) + 1

        return _GeocodeResult(lat=lat, lon=lon, precision=precision, cache_hit=False)
    return None


def _pick_entity(invoice: Invoice, roles: tuple[EntityRole, ...]) -> Entity | None:
    for role in roles:
        for ent in invoice.entities:
            if ent.role == role:
                return ent
    return None


def _source_location(invoice: Invoice) -> _Location | None:
    ent = _pick_entity(invoice, (EntityRole.CONSIGNOR, EntityRole.SELLER))
    if ent is None:
        return None
    return _Location(
        name=_clean_text(ent.name),
        country=_clean_country(ent.country),
        address=_clean_text(ent.address),
        city_hint=None,
    )


def _destination_location(invoice: Invoice) -> _Location | None:
    ent = _pick_entity(
        invoice,
        (EntityRole.CONSIGNEE, EntityRole.BUYER, EntityRole.END_USER, EntityRole.DELIVERY_ADDRESS),
    )
    if ent is None:
        return None
    return _Location(
        name=_clean_text(ent.name),
        country=_clean_country(ent.country) or _clean_country(invoice.destination_country),
        address=_clean_text(ent.address),
        city_hint=None,
    )


def _risk_level(invoice: Invoice, screening_hits: int) -> str:
    if invoice.compliance_score == ComplianceScore.RED:
        return "high"
    if invoice.compliance_score == ComplianceScore.YELLOW:
        return "medium"
    if screening_hits > 0:
        return "medium"
    return "low"


def _risk_rank(level: str) -> int:
    return {"low": 1, "medium": 2, "high": 3}.get(level, 0)


def _decimal_to_str(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


async def build_shipments_map(
    session: AsyncSession,
    *,
    limit: int = 200,
    risk: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    max_external_lookups: int | None = None,
) -> ShipmentMapResponse:
    settings = get_settings()
    budget = _GeocodeBudget(
        max_external_calls=max_external_lookups
        if max_external_lookups is not None
        else settings.geocode_max_external_lookups_per_request
    )

    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.entities))
        .order_by(Invoice.created_at.desc())
        .limit(max(1, min(limit, 1000)))
    )
    if date_from is not None:
        stmt = stmt.where(Invoice.created_at >= datetime.combine(date_from, dtime.min, tzinfo=UTC))
    if date_to is not None:
        stmt = stmt.where(Invoice.created_at <= datetime.combine(date_to, dtime.max, tzinfo=UTC))
    invoices = list((await session.execute(stmt)).scalars().all())

    hit_rows = await session.execute(
        select(ScreeningResult.invoice_id, func.count(ScreeningResult.id))
        .where(ScreeningResult.status != MatchStatus.CLEAR)
        .group_by(ScreeningResult.invoice_id)
    )
    screening_hits_by_invoice = {row[0]: int(row[1]) for row in hit_rows.all()}

    items: list[ShipmentMapRoute] = []
    missing_location_count = 0

    for invoice in invoices:
        src = _source_location(invoice)
        dst = _destination_location(invoice)
        if src is None or dst is None:
            missing_location_count += 1
            continue

        src_geo = await _geocode_location(session, loc=src, budget=budget)
        dst_geo = await _geocode_location(session, loc=dst, budget=budget)
        if src_geo is None or dst_geo is None:
            missing_location_count += 1
            continue

        screening_hits = screening_hits_by_invoice.get(invoice.id, 0)
        level = _risk_level(invoice, screening_hits)
        if risk in {"low", "medium", "high"} and level != risk:
            continue

        low_precision = src_geo.precision == "country" or dst_geo.precision == "country"
        items.append(
            ShipmentMapRoute(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                original_filename=invoice.original_filename,
                invoice_date=invoice.invoice_date,
                total_amount=_decimal_to_str(invoice.total_amount),
                currency=invoice.currency,
                compliance_score=(invoice.compliance_score.value if invoice.compliance_score else None),
                risk_level=level,
                screening_hits=screening_hits,
                source=ShipmentMapPoint(
                    name=src.name,
                    country=src.country,
                    address=src.address,
                    city=src.city_hint,
                    lat=src_geo.lat,
                    lon=src_geo.lon,
                    geo_precision=src_geo.precision,
                ),
                destination=ShipmentMapPoint(
                    name=dst.name,
                    country=dst.country,
                    address=dst.address,
                    city=dst.city_hint,
                    lat=dst_geo.lat,
                    lon=dst_geo.lon,
                    geo_precision=dst_geo.precision,
                ),
                low_precision_line=low_precision,
            )
        )

    items.sort(
        key=lambda x: (_risk_rank(x.risk_level), x.invoice_date or datetime.min.date()),
        reverse=True,
    )
    await session.commit()
    return ShipmentMapResponse(
        total_routes=len(items),
        missing_location_count=missing_location_count,
        geocode_cache_hits=budget.cache_hits,
        geocode_external_calls=budget.external_calls,
        items=items,
    )
