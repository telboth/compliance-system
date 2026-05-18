"""Utvidet screening-tjeneste (MVP+) med Wikidata og enkel web-berikelse."""

from __future__ import annotations

import asyncio
import json
import re
import uuid
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from html import unescape
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse, urlunparse

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.models.entity import Entity
from app.models.extended_screen_claim import ExtendedScreenClaim
from app.models.extended_screen_feedback import ExtendedScreenFeedback
from app.models.extended_screen_source import ExtendedScreenSource
from app.models.extended_screening import ExtendedScreenRun
from app.models.external_watchlist_entry import ExternalWatchlistEntry
from app.models.invoice import Invoice
from app.sanctions.yente_client import get_yente_client
from app.services.external_watchlist_service import (
    SOURCE_BRREG_LOOKUP,
    SOURCE_UK_SANCTIONS,
    SOURCE_WORLD_BANK_DEBARRED,
    list_external_source_health,
)

logger = get_logger(__name__)

_WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
_GLEIF_API_URL = "https://api.gleif.org/api/v1/lei-records"
_WIKIPEDIA_SUMMARY_API_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"
_UK_SANCTIONS_CSV_URL = "https://sanctionslist.fcdo.gov.uk/docs/UK-Sanctions-List.csv"
_WORLD_BANK_DEBARRED_API_URL = (
    "https://apigwext.worldbank.org/dvsvc/v1.0/json/"
    "APPLICATION/ADOBE_EXPRNCE_MGR/FIRM/SANCTIONED_FIRM"
)
_OPENCORPORATES_SEARCH_API_URL = "https://api.opencorporates.com/v0.4/companies/search"
_OPENCORPORATES_COMPANY_API_URL = "https://api.opencorporates.com/v0.4/companies"
_DUCKDUCKGO_HTML_SEARCH_URL = "https://html.duckduckgo.com/html/"
_BRREG_ENHETER_API_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
_REQUEST_TIMEOUT_SECONDS = 12.0
_MAX_HTML_BYTES = 250_000
_MAX_WEB_PAGE_BYTES = 350_000
_MAX_WEB_SNIPPET_LEN = 1200
_DDG_DIRECT_BLOCKED_UNTIL = 0.0

_RISK_COUNTRY_CODES = {"RU", "KP", "IR", "SY", "BY", "CU"}
_RISK_COUNTRY_NAMES = {
    "russia",
    "russian federation",
    "north korea",
    "democratic people's republic of korea",
    "iran",
    "syria",
    "belarus",
    "cuba",
}

_LINK_KEYWORDS = (
    "about",
    "management",
    "leadership",
    "team",
    "board",
    "governance",
    "owner",
    "ownership",
    "company",
    "who-we-are",
    "about-us",
    "om-oss",
    "ledelse",
    "styre",
    "eier",
)

_SNIPPET_KEYWORDS = (
    "owner",
    "ownership",
    "board",
    "director",
    "directors",
    "management",
    "leadership",
    "founder",
    "executive",
    "ceo",
    "chair",
    "styre",
    "ledelse",
    "eier",
)
_SNIPPET_NOISE_TERMS = (
    "news",
    "events",
    "learn more",
    "white paper",
    "cookies",
    "privacy policy",
    "terms of use",
    "all rights reserved",
    "subscribe",
    "newsletter",
    "press release",
    "copyright",
)
_SANCTIONS_CUE_TERMS = (
    "sanction",
    "sanctions",
    "designated",
    "restricted party",
    "denied party",
    "asset freeze",
    "eu consolidated list",
    "ofac",
    "sdn list",
    "uk sanctions",
    "un sanctions",
)
_OFFICIAL_SANCTIONS_DOMAINS = {
    "treasury.gov",
    "ofac.treasury.gov",
    "ec.europa.eu",
    "consilium.europa.eu",
    "eeas.europa.eu",
    "gov.uk",
    "sanctionssearch.ofsi.hmtreasury.gov.uk",
    "un.org",
    "opensanctions.org",
}
_HIGH_TRUST_REFERENCE_DOMAINS = {
    "wikipedia.org",
    "wikidata.org",
    "gleif.org",
    "brreg.no",
    "opencorporates.com",
}
_PERSON_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")
_COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b(?:Inc|Ltd|LLC|PLC|GmbH|ASA|AS|AG|BV|S\\.A\\.|S\\.R\\.L\\.)\b"
)

_COMPANY_QIDS = {
    "Q43229",  # organization
    "Q783794",  # company
    "Q14623646",  # fictional organization (still useful for structure)
}
_PERSON_QIDS = {"Q5", "Q15632617"}
_COUNTRY_QIDS = {"Q6256"}
_LOCATION_QIDS = {
    "Q515",  # city
    "Q486972",  # human settlement
    "Q82794",  # geographic region
    "Q618123",  # geographical object
}

_GENERIC_COMPANY_TOKENS = {
    "llc",
    "ltd",
    "inc",
    "corp",
    "company",
    "co",
    "sa",
    "as",
    "plc",
    "gmbh",
    "ag",
    "bv",
    "oy",
    "spa",
    "srl",
}
_LOW_SIGNAL_DESCRIPTORS = {
    "family name",
    "given name",
    "surname",
    "wikimedia disambiguation page",
    "village",
    "municipality",
    "district",
    "album",
    "song",
    "film",
    "taxon",
}
_PERSON_TOKEN_STOPWORDS = {
    "about",
    "organization",
    "menu",
    "main",
    "navigation",
    "news",
    "events",
    "resources",
    "markets",
    "services",
    "solutions",
    "career",
    "careers",
    "profile",
    "company",
    "group",
    "board",
    "director",
    "directors",
    "founder",
    "ceo",
    "chief",
    "executive",
    "president",
    "trademark",
    "date",
    "over",
    "origin",
    "grumman",
    "lockheed",
    "raytheon",
    "nasa",
    "information",
    "systems",
    "technology",
    "technologies",
    "community",
    "force",
    "space",
    "shuttle",
    "research",
    "datasets",
    "documentation",
    "advanced",
    "global",
    "specialized",
    "commercial",
    "politician",
    "newsletter",
    "github",
    "code",
    "search",
    "tracker",
    "sanctions",
    "finder",
    "database",
    "legal",
    "entities",
    "portal",
    "support",
    "insights",
    "features",
    "consultation",
    "stolen",
    "herit",
    "child",
    "kidnappers",
    "components",
    "instruments",
    "weapons",
    "aircraft",
    "marine",
    "vessels",
    "unit",
}
_PERSON_BIOGRAPHY_NOISE = (
    "he has",
    "his expertise",
    "crew member",
    "space shuttle",
    "mission sts-",
    "sought out by",
)

_RELATION_PROPS = {
    "P749": "parent_organization",
    "P127": "owned_by",
    "P112": "founded_by",
    "P169": "chief_executive_officer",
    "P488": "chairperson",
    "P3320": "board_member",
    "P159": "headquarters_location",
    "P17": "country",
    "P27": "country_of_citizenship",
    "P108": "employer",
    "P463": "member_of",
}
_SANCTIONS_NEAR_RELATIONS = {
    "parent_organization",
    "owned_by",
    "founded_by",
    "chief_executive_officer",
    "chairperson",
    "board_member",
    "employer",
    "member_of",
}


@dataclass(frozen=True)
class _Profile:
    min_candidate_confidence: float
    max_candidates: int
    max_relations_per_candidate: int
    max_sanctions_checks: int
    max_site_pages: int
    max_site_candidates: int
    min_edge_confidence: float
    max_search_queries: int
    max_search_results_per_query: int
    max_search_pages_to_fetch: int
    max_snippets_per_page: int


@dataclass(frozen=True)
class _Candidate:
    qid: str
    label: str
    description: str | None
    aliases: list[str]
    confidence: float


def _default_run_config() -> dict[str, Any]:
    return {
        "min_edge_confidence": 0.6,
        "selected_only": True,
        "sanctions_near_only": False,
        "enable_gleif": True,
        "enable_wikidata": True,
        "enable_company_website": True,
        "enable_brreg": True,
        "enable_uk_sanctions": True,
        "enable_world_bank_debarred": True,
        "enable_ai_entity_research": True,
        "enable_ai_web_search": True,
    }


def _normalize_run_config(run_config: dict[str, Any] | None) -> dict[str, Any]:
    merged = {**_default_run_config(), **(run_config or {})}
    try:
        merged["min_edge_confidence"] = float(merged["min_edge_confidence"])
    except (TypeError, ValueError):
        merged["min_edge_confidence"] = 0.6
    merged["min_edge_confidence"] = max(0.0, min(1.0, merged["min_edge_confidence"]))
    merged["selected_only"] = bool(merged["selected_only"])
    merged["sanctions_near_only"] = bool(merged["sanctions_near_only"])
    merged["enable_gleif"] = bool(merged["enable_gleif"])
    merged["enable_wikidata"] = bool(merged["enable_wikidata"])
    merged["enable_company_website"] = bool(merged["enable_company_website"])
    merged["enable_brreg"] = bool(merged["enable_brreg"])
    merged["enable_uk_sanctions"] = bool(merged["enable_uk_sanctions"])
    merged["enable_world_bank_debarred"] = bool(merged["enable_world_bank_debarred"])
    merged["enable_ai_entity_research"] = bool(merged["enable_ai_entity_research"])
    merged["enable_ai_web_search"] = bool(merged["enable_ai_web_search"])
    return merged


def _normalize_text(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", value).lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _seed_tokens(seed_name: str) -> set[str]:
    return {
        token
        for token in _tokenize(seed_name)
        if len(token) >= 4 and token not in _GENERIC_COMPANY_TOKENS
    }


def _is_domain_related_to_seed(source_url: str | None, seed_name: str) -> bool:
    host = _domain_of_url(source_url) or ""
    if not host:
        return False
    host_norm = host.replace("-", " ").replace(".", " ")
    seed = _seed_tokens(seed_name)
    return any(token in host_norm for token in seed)


def _is_snippet_seed_relevant(
    *,
    seed_name: str,
    source_url: str | None,
    snippet: str,
) -> bool:
    lowered = snippet.lower()
    seed = _seed_tokens(seed_name)
    if not seed:
        return False
    token_hit = any(token in lowered for token in seed)
    domain_hit = _is_domain_related_to_seed(source_url, seed_name)
    if not token_hit and not domain_hit:
        return False
    if any(noise in lowered for noise in _PERSON_BIOGRAPHY_NOISE):
        return False
    return True


def _is_plausible_person_name(candidate: str) -> bool:
    tokens = [token.strip().lower() for token in candidate.split() if token.strip()]
    if len(tokens) < 2 or len(tokens) > 3:
        return False
    if any(token in _PERSON_TOKEN_STOPWORDS for token in tokens):
        return False
    if any(len(token) < 2 for token in tokens):
        return False
    return True


def _has_governance_role_cue(snippet: str) -> bool:
    lowered = snippet.lower()
    # Bruk ordgrenser for å unngå falske treff som "directorate".
    patterns = (
        r"\bboard of directors\b",
        r"\bdirectors?\b",
        r"\bchair(?:person)?\b",
        r"\bchief executive\b",
        r"\bceo\b",
        r"\bexecutive team\b",
        r"\bleadership team\b",
        r"\bmanagement team\b",
        r"\bowners?\b",
        r"\bownership\b",
        r"\bshareholders?\b",
        r"\bparent company\b",
        r"\bbeneficial owner\b",
    )
    return any(re.search(pattern, lowered) for pattern in patterns)


def _has_person_role_context(signal: str, start: int, end: int) -> bool:
    left = max(0, start - 80)
    right = min(len(signal), end + 80)
    context = signal[left:right].lower()
    patterns = (
        r"\bdirectors?\b",
        r"\bchair(?:person)?\b",
        r"\bchief executive\b",
        r"\bceo\b",
        r"\bexecutive\b",
        r"\bfounder\b",
        r"\bpresident\b",
        r"\bmanager\b",
        r"\bofficer\b",
    )
    return any(re.search(pattern, context) for pattern in patterns)


def _tokenize(value: str) -> set[str]:
    return {token for token in _normalize_text(value).split(" ") if token}


def _name_similarity(a: str, b: str) -> float:
    left = _normalize_text(a)
    right = _normalize_text(b)
    if not left or not right:
        return 0.0

    ratio = SequenceMatcher(None, left, right).ratio()
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if left_tokens and right_tokens:
        overlap = len(left_tokens & right_tokens) / max(len(left_tokens | right_tokens), 1)
    else:
        overlap = 0.0

    prefix_bonus = 0.0
    if left.startswith(right) or right.startswith(left):
        prefix_bonus = 0.08

    score = (0.65 * ratio) + (0.35 * overlap) + prefix_bonus
    return round(min(score, 1.0), 4)


def _profile_from_aggressiveness(aggressiveness: int) -> _Profile:
    clamped = max(0, min(100, aggressiveness))
    return _Profile(
        min_candidate_confidence=round(0.72 - (clamped / 100.0) * 0.28, 2),
        max_candidates=2 + (clamped // 20),
        max_relations_per_candidate=5 + (clamped // 12),
        max_sanctions_checks=6 + (clamped // 10),
        max_site_pages=1 + (clamped // 25),
        max_site_candidates=2 + (clamped // 40),
        min_edge_confidence=round(0.70 - (clamped / 100.0) * 0.34, 2),
        max_search_queries=8 + (clamped // 6),
        max_search_results_per_query=4 + (clamped // 30),
        max_search_pages_to_fetch=10 + (clamped // 8),
        max_snippets_per_page=3 + (clamped // 40),
    )


def _extract_claim_entity_ids(entity_doc: dict[str, Any], prop: str, *, limit: int) -> list[str]:
    claims = (entity_doc.get("claims") or {}).get(prop) or []
    ids: list[str] = []
    seen: set[str] = set()

    for claim in claims:
        mainsnak = claim.get("mainsnak") or {}
        datavalue = mainsnak.get("datavalue") or {}
        value = datavalue.get("value") or {}
        if not isinstance(value, dict):
            continue

        qid = value.get("id")
        if isinstance(qid, str) and qid:
            if qid not in seen:
                seen.add(qid)
                ids.append(qid)
        elif "numeric-id" in value:
            qid = f"Q{value['numeric-id']}"
            if qid not in seen:
                seen.add(qid)
                ids.append(qid)

        if len(ids) >= limit:
            break

    return ids


def _extract_claim_strings(entity_doc: dict[str, Any], prop: str, *, limit: int) -> list[str]:
    claims = (entity_doc.get("claims") or {}).get(prop) or []
    values: list[str] = []
    seen: set[str] = set()

    for claim in claims:
        mainsnak = claim.get("mainsnak") or {}
        datavalue = mainsnak.get("datavalue") or {}
        value = datavalue.get("value")
        if not isinstance(value, str):
            continue
        trimmed = value.strip()
        if not trimmed or trimmed in seen:
            continue
        seen.add(trimmed)
        values.append(trimmed)
        if len(values) >= limit:
            break

    return values


def _label_of(entity_doc: dict[str, Any]) -> str | None:
    labels = entity_doc.get("labels") or {}
    for lang in ("en", "nb", "nn", "no"):
        item = labels.get(lang)
        if isinstance(item, dict) and isinstance(item.get("value"), str):
            value = item["value"].strip()
            if value:
                return value
    if isinstance(labels, dict):
        for item in labels.values():
            if isinstance(item, dict) and isinstance(item.get("value"), str):
                value = item["value"].strip()
                if value:
                    return value
    return None


def _description_of(entity_doc: dict[str, Any]) -> str | None:
    descriptions = entity_doc.get("descriptions") or {}
    for lang in ("en", "nb", "nn", "no"):
        item = descriptions.get(lang)
        if isinstance(item, dict) and isinstance(item.get("value"), str):
            value = item["value"].strip()
            if value:
                return value
    return None


def _item_type(entity_doc: dict[str, Any]) -> str:
    p31_ids = set(_extract_claim_entity_ids(entity_doc, "P31", limit=8))
    if p31_ids & _PERSON_QIDS:
        return "person"
    if p31_ids & _COUNTRY_QIDS:
        return "country"
    if p31_ids & _LOCATION_QIDS:
        return "location"
    if p31_ids & _COMPANY_QIDS:
        return "company"
    return "unknown"


def _iso2_candidates_from_text(text: str) -> list[str]:
    tokens = _tokenize(text)
    codes = [token.upper() for token in tokens if len(token) == 2 and token.isalpha()]
    return list(dict.fromkeys(codes))


def _normalize_url(raw: str) -> str | None:
    try:
        parsed = urlparse(raw.strip())
    except Exception:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    clean = parsed._replace(fragment="")
    return urlunparse(clean)


def _domain_of_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    return parsed.netloc.lower() or None


async def _gleif_search(
    client: httpx.AsyncClient,
    legal_name: str,
    *,
    page_size: int = 5,
) -> list[dict[str, Any]]:
    params = {
        "filter[entity.legalName]": legal_name,
        "page[size]": max(1, min(page_size, 10)),
    }
    response = await client.get(_GLEIF_API_URL, params=params)
    response.raise_for_status()
    data = response.json()
    rows = data.get("data") or []
    return rows if isinstance(rows, list) else []


async def _wikidata_search(
    client: httpx.AsyncClient,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    params = {
        "action": "wbsearchentities",
        "search": query,
        "language": "en",
        "uselang": "en",
        "type": "item",
        "format": "json",
        "limit": limit,
    }
    response = await client.get(_WIKIDATA_API_URL, params=params)
    response.raise_for_status()
    data = response.json()
    hits = data.get("search") or []
    return hits if isinstance(hits, list) else []


async def _wikidata_get_entities(
    client: httpx.AsyncClient,
    qids: list[str],
) -> dict[str, dict[str, Any]]:
    if not qids:
        return {}

    entities: dict[str, dict[str, Any]] = {}
    chunk_size = 40
    for i in range(0, len(qids), chunk_size):
        chunk = qids[i : i + chunk_size]
        params = {
            "action": "wbgetentities",
            "ids": "|".join(chunk),
            "languages": "en|nb|nn|no",
            "props": "labels|descriptions|claims|sitelinks",
            "format": "json",
        }
        response = await client.get(_WIKIDATA_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        rows = data.get("entities") or {}
        if isinstance(rows, dict):
            for qid, entity in rows.items():
                if isinstance(entity, dict):
                    entities[qid] = entity

    return entities


def _build_candidates(
    seed_name: str,
    search_hits: list[dict[str, Any]],
    profile: _Profile,
) -> list[_Candidate]:
    candidates: list[_Candidate] = []

    for hit in search_hits:
        qid = str(hit.get("id") or "").strip()
        if not qid:
            continue

        label = str(hit.get("label") or "").strip()
        description = str(hit.get("description") or "").strip() or None

        aliases_raw = hit.get("aliases") or []
        aliases = [str(alias).strip() for alias in aliases_raw if str(alias).strip()]

        best = _name_similarity(seed_name, label)
        for alias in aliases:
            best = max(best, _name_similarity(seed_name, alias))

        if best < profile.min_candidate_confidence:
            continue

        candidates.append(
            _Candidate(
                qid=qid,
                label=label or qid,
                description=description,
                aliases=aliases,
                confidence=best,
            )
        )

    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates[: profile.max_candidates]


def _relation_target_type(relation: str) -> str:
    if relation in {"country", "country_of_citizenship"}:
        return "country"
    if relation == "headquarters_location":
        return "location"
    if relation in {
        "chief_executive_officer",
        "chairperson",
        "board_member",
        "founded_by",
    }:
        return "person"
    if relation in {
        "parent_organization",
        "owned_by",
        "employer",
        "member_of",
    }:
        return "company"
    return "company"


def _is_low_signal_description(description: str | None) -> bool:
    if not description:
        return False
    lowered = description.lower()
    return any(flag in lowered for flag in _LOW_SIGNAL_DESCRIPTORS)


def _is_generic_company_name(name: str) -> bool:
    tokens = [token for token in _tokenize(name) if token]
    if not tokens:
        return True
    if len(tokens) > 3:
        return False
    return all(token in _GENERIC_COMPANY_TOKENS for token in tokens)


def _candidate_allowed_for_seed(
    *,
    seed_entity: Entity,
    candidate: _Candidate,
    candidate_type: str,
    description: str | None,
) -> tuple[bool, str]:
    if _is_low_signal_description(description):
        return False, "low_signal_description"

    expected_type = (
        "person" if seed_entity.entity_type.value == "person" else "company"
    )

    if candidate_type != expected_type:
        return False, "type_mismatch"

    if candidate.confidence < 0.82:
        return False, "low_name_confidence"

    if expected_type == "company" and _is_generic_company_name(candidate.label):
        return False, "generic_company_name"

    return True, "ok"


def _is_plausible_sanctions_hit(
    *,
    target_name: str,
    matched_name: str | None,
    match_score: float,
) -> tuple[bool, str]:
    if _is_generic_company_name(target_name):
        return False, "generic_target_name"

    if not matched_name:
        return False, "missing_matched_name"

    similarity = _name_similarity(target_name, matched_name)
    if match_score >= 0.92:
        return True, "very_high_score_override"

    if similarity < 0.78:
        return False, f"low_name_similarity:{similarity:.2f}"

    return True, "ok"


def _clean_html_to_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_internal_links(html: str, base_url: str, max_links: int) -> list[str]:
    base = urlparse(base_url)
    if not base.netloc:
        return []

    links: list[str] = []
    seen: set[str] = set()

    for match in re.finditer(r"""href\s*=\s*['"]([^'"]+)['"]""", html, flags=re.IGNORECASE):
        href = match.group(1).strip()
        if not href or href.startswith("#"):
            continue

        absolute = _normalize_url(urljoin(base_url, href))
        if not absolute:
            continue

        parsed = urlparse(absolute)
        if parsed.netloc != base.netloc:
            continue

        hay = f"{parsed.path} {parsed.query}".lower()
        if not any(keyword in hay for keyword in _LINK_KEYWORDS):
            continue

        if absolute in seen:
            continue
        seen.add(absolute)
        links.append(absolute)

        if len(links) >= max_links:
            break

    return links


def _extract_keyword_snippets(text: str, max_snippets: int) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    snippets: list[str] = []
    seen: set[str] = set()

    for part in parts:
        sentence = part.strip()
        if len(sentence) < 24:
            continue

        lowered = sentence.lower()
        if not any(keyword in lowered for keyword in _SNIPPET_KEYWORDS):
            continue
        if any(noise in lowered for noise in _SNIPPET_NOISE_TERMS):
            continue

        has_person_name = bool(_PERSON_NAME_PATTERN.search(sentence))
        has_company_suffix = bool(_COMPANY_SUFFIX_PATTERN.search(sentence))
        has_ownership_signal = any(
            keyword in lowered
            for keyword in (
                "owner",
                "ownership",
                "board",
                "director",
                "founder",
                "ceo",
                "chair",
                "styre",
                "ledelse",
                "eier",
            )
        )
        # Presisjonsmodus: krev både relevant tema og plausibelt subjekt.
        if has_ownership_signal and not (has_person_name or has_company_suffix):
            continue

        short = sentence[:300]
        if short in seen:
            continue
        seen.add(short)
        snippets.append(short)

        if len(snippets) >= max_snippets:
            break

    return snippets


async def _fetch_page_text(client: httpx.AsyncClient, url: str) -> tuple[str | None, str | None]:
    last_error = "unknown error"
    for attempt in range(2):
        try:
            response = await client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return None, f"unsupported content-type: {content_type}"

            html = response.text[:_MAX_WEB_PAGE_BYTES]
            text = _clean_html_to_text(html)
            return text, html
        except Exception as exc:
            last_error = str(exc)
            if attempt == 0:
                await asyncio.sleep(0.2)
    return None, last_error


async def _scan_company_website(
    client: httpx.AsyncClient,
    website_url: str,
    profile: _Profile,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "website": website_url,
        "pages": [],
        "errors": [],
        "owner_board_management_signals": [],
    }

    text, html_or_error = await _fetch_page_text(client, website_url)
    if text is None:
        result["errors"].append({"url": website_url, "error": html_or_error})
        return result

    homepage_html = html_or_error or ""
    homepage_snippets = _extract_keyword_snippets(text, max_snippets=8)
    result["pages"].append(
        {
            "url": website_url,
            "snippet_count": len(homepage_snippets),
            "snippets": homepage_snippets,
        }
    )
    result["owner_board_management_signals"].extend(homepage_snippets)

    links = _extract_internal_links(
        homepage_html,
        website_url,
        max_links=max(profile.max_site_pages, 1),
    )

    for link in links[: profile.max_site_pages]:
        page_text, page_html_or_error = await _fetch_page_text(client, link)
        if page_text is None:
            result["errors"].append({"url": link, "error": page_html_or_error})
            continue

        snippets = _extract_keyword_snippets(page_text, max_snippets=6)
        result["pages"].append(
            {
                "url": link,
                "snippet_count": len(snippets),
                "snippets": snippets,
            }
        )
        result["owner_board_management_signals"].extend(snippets)

    deduped_signals = list(dict.fromkeys(result["owner_board_management_signals"]))
    result["owner_board_management_signals"] = deduped_signals[:20]
    result["pages_scanned"] = len(result["pages"])

    return result


def _wikipedia_page_url_from_doc(entity_doc: dict[str, Any]) -> str | None:
    sitelinks = entity_doc.get("sitelinks") or {}
    if not isinstance(sitelinks, dict):
        return None
    enwiki = sitelinks.get("enwiki") or sitelinks.get("nowiki")
    if not isinstance(enwiki, dict):
        return None
    title = str(enwiki.get("title") or "").strip()
    if not title:
        return None
    return f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"


async def _fetch_wikipedia_summary(
    client: httpx.AsyncClient,
    wikipedia_url: str,
) -> dict[str, Any] | None:
    parsed = urlparse(wikipedia_url)
    if "wikipedia.org" not in parsed.netloc:
        return None
    title = parsed.path.rsplit("/", 1)[-1].strip()
    if not title:
        return None
    summary_url = f"{_WIKIPEDIA_SUMMARY_API_URL}/{title}"
    try:
        response = await client.get(summary_url)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    extract = str(payload.get("extract") or "").strip()
    if not extract:
        return None
    content_urls = payload.get("content_urls") or {}
    desktop = content_urls.get("desktop") if isinstance(content_urls, dict) else {}
    page_url = (
        str((desktop or {}).get("page") or "").strip()
        if isinstance(desktop, dict)
        else ""
    )
    return {
        "provider": "wikipedia",
        "source_url": page_url or wikipedia_url,
        "title": str(payload.get("title") or "").strip() or None,
        "excerpt": extract[:1000],
    }


async def _opencorporates_search_companies(
    client: httpx.AsyncClient,
    *,
    name: str,
    api_token: str | None,
    max_results: int = 2,
) -> list[dict[str, Any]]:
    query = name.strip()
    if len(query) < 4:
        return []
    params: dict[str, Any] = {"q": query, "per_page": max(1, min(5, max_results))}
    if api_token:
        params["api_token"] = api_token
    try:
        response = await client.get(_OPENCORPORATES_SEARCH_API_URL, params=params)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    raw_rows = ((payload or {}).get("results") or {}).get("companies") or []
    if not isinstance(raw_rows, list):
        return []

    out: list[dict[str, Any]] = []
    for row in raw_rows:
        item = (row or {}).get("company") if isinstance(row, dict) else None
        if not isinstance(item, dict):
            continue
        company_name = str(item.get("name") or "").strip()
        if not company_name:
            continue
        if _name_similarity(query, company_name) < 0.82:
            continue
        out.append(item)
        if len(out) >= max_results:
            break
    return out


async def _opencorporates_fetch_company(
    client: httpx.AsyncClient,
    *,
    jurisdiction_code: str,
    company_number: str,
    api_token: str | None,
) -> dict[str, Any] | None:
    if not jurisdiction_code or not company_number:
        return None
    params: dict[str, Any] = {}
    if api_token:
        params["api_token"] = api_token
    url = (
        f"{_OPENCORPORATES_COMPANY_API_URL}/"
        f"{quote(jurisdiction_code)}/{quote(company_number)}"
    )
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    company = ((payload or {}).get("results") or {}).get("company") or {}
    return company if isinstance(company, dict) else None


def _strip_html_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "").strip()


def _unwrap_duckduckgo_redirect(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query or "")
    uddg = query.get("uddg") or []
    if uddg:
        return unquote(str(uddg[0]))
    return url


def _is_search_result_url_allowed(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host:
        return False
    blocked_hosts = (
        "duckduckgo.com",
        "bing.com",
        "msn.com",
        "youtube.com",
        "facebook.com",
        "x.com",
        "twitter.com",
        "instagram.com",
        "linkedin.com",
    )
    return not any(host.endswith(item) for item in blocked_hosts)


def _canonicalize_domain(domain: str | None) -> str:
    value = str(domain or "").strip().lower()
    if value.startswith("www."):
        value = value[4:]
    return value


def _domain_matches_allowlist(domain: str | None, allowlist: set[str]) -> bool:
    host = _canonicalize_domain(domain)
    if not host:
        return False
    for allowed in allowlist:
        if not allowed:
            continue
        if host == allowed or host.endswith(f".{allowed}"):
            return True
    return False


def _is_registry_or_generic_domain(domain: str | None) -> bool:
    host = _canonicalize_domain(domain)
    if not host:
        return True
    blocked = (
        "wikipedia.org",
        "wikidata.org",
        "opencorporates.com",
        "brreg.no",
        "duckduckgo.com",
    )
    return any(host == item or host.endswith(f".{item}") for item in blocked)


def _domain_in_set(domain: str | None, allowed: set[str]) -> bool:
    host = _canonicalize_domain(domain)
    if not host:
        return False
    for entry in allowed:
        canon = _canonicalize_domain(entry)
        if host == canon or host.endswith(f".{canon}"):
            return True
    return False


def _is_official_sanctions_domain(domain: str | None) -> bool:
    return _domain_in_set(domain, _OFFICIAL_SANCTIONS_DOMAINS)


def _is_high_trust_domain(domain: str | None) -> bool:
    return _is_official_sanctions_domain(domain) or _domain_in_set(
        domain,
        _HIGH_TRUST_REFERENCE_DOMAINS,
    )


def _source_tier(provider: str | None, source_url: str | None) -> str:
    provider_norm = str(provider or "").strip().lower()
    domain = _canonicalize_domain(_domain_of_url(source_url))
    if provider_norm in {
        "uk_sanctions",
        "world_bank_debarred",
        "gleif",
        "brreg",
        "yente",
        "sanctions_match",
    }:
        return "official"
    if _is_official_sanctions_domain(domain):
        return "official"
    if _is_high_trust_domain(domain):
        return "reference"
    if provider_norm in {
        "duckduckgo_search",
        "duckduckgo_proxy_search",
        "bing_search",
        "company_website",
        "ai_synthesis",
    }:
        return "discovery"
    return "unknown"


def _has_sanctions_cue(snippet: str) -> bool:
    lowered = snippet.lower()
    return any(token in lowered for token in _SANCTIONS_CUE_TERMS)


def _build_research_queries(seed_name: str) -> list[str]:
    name = seed_name.strip()
    if not name:
        return []
    return [
        f"\"{name}\" sanctions",
        f"\"{name}\" sanctioned entity",
        f"\"{name}\" ownership structure",
        f"\"{name}\" shareholders",
        f"\"{name}\" beneficial owner",
        f"\"{name}\" ultimate parent company",
        f"\"{name}\" board of directors",
        f"\"{name}\" executive leadership",
        f"\"{name}\" governance report",
        f"\"{name}\" connected to Russia",
        f"\"{name}\" export control",
        f"{name} actionnaires direction",
    ]


def _build_domain_research_queries(seed_name: str, domains: set[str]) -> list[str]:
    name = seed_name.strip()
    if not name:
        return []
    rows: list[str] = []
    for domain in sorted(domains):
        rows.extend(
            [
                f'site:{domain} "{name}" sanctions',
                f'site:{domain} "{name}" ownership',
                f'site:{domain} "{name}" board of directors',
                f'site:{domain} "{name}" executive leadership',
                f'site:{domain} "{name}" governance',
            ]
        )
    return rows


def _dedupe_keep_order(rows: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        key = row.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


async def _duckduckgo_html_search(
    client: httpx.AsyncClient,
    *,
    query: str,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    global _DDG_DIRECT_BLOCKED_UNTIL
    async def _extract_from_html(html: str, provider: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        pattern = re.compile(
            r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            flags=re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(html):
            raw_href = str(match.group(1) or "").strip()
            raw_title = str(match.group(2) or "").strip()
            if not raw_href:
                continue
            url = _unwrap_duckduckgo_redirect(raw_href)
            if not _is_search_result_url_allowed(url):
                continue
            url_norm = str(url).strip()
            if not url_norm or url_norm in seen_urls:
                continue
            seen_urls.add(url_norm)
            title = _strip_html_tags(raw_title)
            rows.append(
                {
                    "source_provider": provider,
                    "query": query,
                    "title": title[:512] or None,
                    "source_url": url_norm,
                }
            )
            if len(rows) >= max_results:
                break
        return rows

    async def _proxy_search_via_jina() -> list[dict[str, Any]]:
        proxy_url = "https://r.jina.ai/http://html.duckduckgo.com/html/"
        try:
            response = await client.get(proxy_url, params={"q": query})
            response.raise_for_status()
            text = response.text[:900_000]
        except Exception as exc:
            logger.warning("extended_screen_ddg_proxy_search_failed", query=query, error=str(exc))
            return []

        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for match in re.finditer(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text):
            raw_title = str(match.group(1) or "").strip()
            raw_href = str(match.group(2) or "").strip()
            if not raw_href or not raw_title:
                continue
            url = _unwrap_duckduckgo_redirect(raw_href)
            if not _is_search_result_url_allowed(url):
                continue
            url_norm = str(url).strip()
            if not url_norm or url_norm in seen_urls:
                continue
            seen_urls.add(url_norm)
            rows.append(
                {
                    "source_provider": "duckduckgo_proxy_search",
                    "query": query,
                    "title": _strip_html_tags(raw_title)[:512] or None,
                    "source_url": url_norm,
                }
            )
            if len(rows) >= max_results:
                break
        return rows

    now = time.monotonic()
    if now < _DDG_DIRECT_BLOCKED_UNTIL:
        return await _proxy_search_via_jina()

    try:
        response = await client.post(
            _DUCKDUCKGO_HTML_SEARCH_URL,
            data={"q": query},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            },
        )
        response.raise_for_status()
        html = response.text[:900_000]
        rows = await _extract_from_html(html, "duckduckgo_search")
        if rows:
            return rows
    except Exception as exc:
        logger.warning("extended_screen_ddg_search_failed", query=query, error=str(exc))
        # DDG er ofte blokkert i enkelte driftmiljø. Unngå timeout på hvert query.
        _DDG_DIRECT_BLOCKED_UNTIL = time.monotonic() + 900.0

    proxy_rows = await _proxy_search_via_jina()
    return proxy_rows


def _role_bucket_from_relation(relation: str) -> str | None:
    relation_key = relation.strip().lower()
    if relation_key in {"parent_organization"}:
        return "ultimate_parent"
    if relation_key in {"owned_by"}:
        return "direct_owner"
    if relation_key in {"beneficial_owner"}:
        return "beneficial_owner"
    if relation_key in {"chief_executive_officer", "ceo", "executive_link"}:
        return "executive"
    if relation_key in {"chairperson", "board_member", "board_link"}:
        return "board_member"
    if relation_key in {"brreg_role_holder", "director", "officer"}:
        return "board_member"
    return None


def _dedupe_profile_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        name = str(row.get("name") or "").strip()
        if len(name) < 3:
            continue
        role = str(row.get("role") or "unknown").strip().lower()
        source = str(row.get("source_provider") or "unknown").strip().lower()
        key = (_normalize_text(name), role, source)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    out.sort(
        key=lambda item: float(item.get("confidence") or 0.0),
        reverse=True,
    )
    return out


def _safe_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        pass
    first = text.find("{")
    last = text.rfind("}")
    if first >= 0 and last > first:
        try:
            parsed = json.loads(text[first : last + 1])
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


async def _ai_extract_ownership_profile(
    *,
    seed_name: str,
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = get_settings()
    api_key = settings.openai_api_key_value
    if not api_key or not evidence_rows:
        return {}
    top_rows = evidence_rows[:24]
    evidence_text = "\n".join(
        (
            f"- provider={row.get('source_provider')} "
            f"url={row.get('source_url')} "
            f"excerpt={str(row.get('evidence_excerpt') or '')[:380]}"
        )
        for row in top_rows
    )
    prompt = (
        "Extract ownership and management facts for compliance due diligence.\n"
        f"Entity: {seed_name}\n"
        "Use only explicit facts from evidence. Do not invent.\n"
        "Return JSON with keys: "
        "ultimate_parent, direct_owners, beneficial_owners, board_members, executives.\n"
        "Each list item/object must include: "
        "name, role, confidence, evidence_excerpt, source_url.\n"
        "If unknown, use null or empty list.\n"
        "Evidence:\n"
        f"{evidence_text}"
    )
    try:
        from openai import AsyncOpenAI  # lazy import

        client = AsyncOpenAI(api_key=api_key, timeout=settings.extended_screen_ai_timeout_seconds)
        response = await client.chat.completions.create(
            model=settings.extended_screen_ai_model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a strict compliance research extractor."},
                {"role": "user", "content": prompt},
            ],
        )
    except Exception as exc:
        logger.warning("extended_screen_ai_extract_failed", error=str(exc))
        return {}

    content = ""
    try:
        content = str(response.choices[0].message.content or "")
    except Exception:
        return {}
    return _safe_json_object(content)


async def _ai_summarize_web_findings(
    *,
    seed_name: str,
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    settings = get_settings()
    api_key = settings.openai_api_key_value
    if not api_key or not evidence_rows:
        return {}

    lines: list[str] = []
    for row in evidence_rows[:20]:
        provider = str(row.get("source_provider") or "unknown")
        source_url = str(row.get("source_url") or "")
        excerpt = str(row.get("evidence_excerpt") or "")[:380]
        if not excerpt:
            continue
        lines.append(f"- provider={provider} url={source_url} excerpt={excerpt}")
    if not lines:
        return {}

    prompt = (
        "You are summarizing web research for compliance due diligence.\n"
        f"Entity: {seed_name}\n"
        "Use only the evidence below. Never invent facts.\n"
        "Return strict JSON with keys: summary_text, key_claims.\n"
        "key_claims must be an array of objects with keys: claim, source_url, quote, confidence.\n"
        "Only include claims with explicit quote support.\n"
        "Evidence:\n"
        + "\n".join(lines)
    )

    try:
        from openai import AsyncOpenAI  # lazy import

        client = AsyncOpenAI(api_key=api_key, timeout=settings.extended_screen_ai_timeout_seconds)
        response = await client.chat.completions.create(
            model=settings.extended_screen_ai_model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a strict compliance analyst."},
                {"role": "user", "content": prompt},
            ],
        )
        content = str(response.choices[0].message.content or "")
    except Exception as exc:
        logger.warning("extended_screen_ai_web_summary_failed", error=str(exc))
        return {}

    parsed = _safe_json_object(content)
    if not parsed:
        return {}
    claims = parsed.get("key_claims")
    if not isinstance(claims, list):
        parsed["key_claims"] = []
    return parsed


def _extract_profile_rows_from_ai(
    ai_payload: dict[str, Any],
    *,
    fallback_source_provider: str = "ai_synthesis",
    seed_name: str | None = None,
) -> dict[str, Any]:
    def _rows(value: Any, default_role: str) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            return []
        out: list[dict[str, Any]] = []
        for row in value:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            if len(name) < 3:
                continue
            if (
                default_role in {"board_member", "executive"}
                and not _is_plausible_person_name(name)
            ):
                continue
            conf = row.get("confidence")
            if not isinstance(conf, float | int):
                conf = 0.62
            source_url = _normalize_url(str(row.get("source_url") or "").strip())
            evidence_excerpt = str(row.get("evidence_excerpt") or "").strip()[:1024] or None
            if seed_name and evidence_excerpt:
                if not _is_snippet_seed_relevant(
                    seed_name=seed_name,
                    source_url=source_url,
                    snippet=evidence_excerpt,
                ):
                    continue
            out.append(
                {
                    "name": name[:512],
                    "role": str(row.get("role") or default_role)[:128],
                    "confidence": float(conf),
                    "source_provider": fallback_source_provider,
                    "source_url": source_url,
                    "evidence_excerpt": evidence_excerpt,
                    "published_at": None,
                    "verification_status": "unverified",
                }
            )
        return out

    ultimate_parent = ai_payload.get("ultimate_parent")
    parent_rows = _rows(ultimate_parent, "ultimate_parent")
    return {
        "ultimate_parent": parent_rows[0] if parent_rows else None,
        "direct_owners": _rows(ai_payload.get("direct_owners"), "direct_owner"),
        "beneficial_owners": _rows(ai_payload.get("beneficial_owners"), "beneficial_owner"),
        "board_members": _rows(ai_payload.get("board_members"), "board_member"),
        "executives": _rows(ai_payload.get("executives"), "executive"),
    }


async def _build_ownership_management_profile(
    client: httpx.AsyncClient,
    *,
    query_profile: _Profile,
    seed_name: str,
    seed_country: str | None,
    selected_candidates: list[_Candidate],
    candidate_docs: dict[str, dict[str, Any]],
    associations: list[dict[str, Any]],
    website_findings: list[dict[str, Any]],
    brreg_findings: list[dict[str, Any]],
    enable_ai_entity_research: bool,
    enable_ai_web_search: bool,
) -> dict[str, Any]:
    settings = get_settings()
    evidence_rows: list[dict[str, Any]] = []
    profile: dict[str, Any] = {
        "ultimate_parent": None,
        "direct_owners": [],
        "beneficial_owners": [],
        "board_members": [],
        "executives": [],
        "source_evidence": [],
        "external_profiles": [],
        "screening_hits": [],
        "risk_country_signals": [],
        "diagnostics": [],
        "web_research": {
            "queries_planned": 0,
            "queries_executed": 0,
            "results_found": 0,
            "pages_fetched": 0,
            "pages_with_signal": 0,
            "fetch_errors": 0,
        },
        "ai_web_summary": None,
        "ai_web_claims": [],
    }

    for assoc in associations:
        if not isinstance(assoc, dict):
            continue
        relation = str(assoc.get("relation") or "").strip()
        bucket = _role_bucket_from_relation(relation)
        if not bucket:
            continue
        target = assoc.get("target") or {}
        if not isinstance(target, dict):
            continue
        name = str(target.get("name") or "").strip()
        if len(name) < 3:
            continue
        source_provider = str(assoc.get("source") or "wikidata").strip() or "wikidata"
        source_qid = str(assoc.get("source_qid") or "").strip()
        source_url = str(assoc.get("source_url") or "").strip() or None
        if not source_url and source_qid and source_provider == "wikidata":
            source_url = f"https://www.wikidata.org/wiki/{source_qid}"
        confidence = _confidence_value(assoc.get("edge_confidence")) or 0.70
        excerpt = f"{seed_name} --{relation}--> {name}"
        row = {
            "name": name[:512],
            "role": relation[:128],
            "confidence": confidence,
            "source_provider": source_provider[:32],
            "source_url": source_url,
            "evidence_excerpt": excerpt[:1024],
            "published_at": None,
            "verification_status": _verification_from_confidence(confidence),
        }
        evidence_rows.append(row)
        if bucket == "ultimate_parent":
            current = profile.get("ultimate_parent")
            if (
                not isinstance(current, dict)
                or float(current.get("confidence") or 0.0) < confidence
            ):
                profile["ultimate_parent"] = row
        elif bucket == "direct_owner":
            profile["direct_owners"].append(row)
        elif bucket == "beneficial_owner":
            profile["beneficial_owners"].append(row)
        elif bucket == "board_member":
            profile["board_members"].append(row)
        elif bucket == "executive":
            profile["executives"].append(row)

    for finding in website_findings:
        if not isinstance(finding, dict):
            continue
        website_url = str(finding.get("website") or "").strip() or None
        signals = finding.get("owner_board_management_signals") or []
        if not isinstance(signals, list):
            continue
        for signal in signals[:12]:
            signal_text = str(signal).strip()
            if len(signal_text) < 20:
                continue
            evidence_rows.append(
                {
                    "name": seed_name[:512],
                    "role": "website_governance_signal",
                    "confidence": 0.62,
                    "source_provider": "company_website",
                    "source_url": website_url,
                    "evidence_excerpt": signal_text[:1024],
                    "published_at": None,
                    "verification_status": "unverified",
                }
            )

    seen_wiki: set[str] = set()
    for candidate in selected_candidates[:4]:
        doc = candidate_docs.get(candidate.qid) or {}
        wiki_url = _wikipedia_page_url_from_doc(doc)
        if not wiki_url or wiki_url in seen_wiki:
            continue
        seen_wiki.add(wiki_url)
        summary = await _fetch_wikipedia_summary(client, wiki_url)
        if not summary:
            continue
        profile["external_profiles"].append(summary)
        excerpt = str(summary.get("excerpt") or "").strip()
        if excerpt:
            evidence_rows.append(
                {
                    "name": candidate.label[:512],
                    "role": "wikipedia_profile",
                    "confidence": 0.58,
                    "source_provider": "wikipedia",
                    "source_url": str(summary.get("source_url") or wiki_url),
                    "evidence_excerpt": excerpt[:1024],
                    "published_at": None,
                    "verification_status": "unverified",
                }
            )
    if not seen_wiki:
        profile["diagnostics"].append("Ingen Wikipedia-side funnet via valgte Wikidata-kandidater.")

    oc_token = settings.opencorporates_api_token.strip() or None
    oc_companies = await _opencorporates_search_companies(
        client,
        name=seed_name,
        api_token=oc_token,
        max_results=2,
    )
    for company in oc_companies:
        jurisdiction = str(company.get("jurisdiction_code") or "").strip()
        company_number = str(company.get("company_number") or "").strip()
        company_name = str(company.get("name") or "").strip() or seed_name
        company_url = str(company.get("opencorporates_url") or "").strip() or None
        if company_url:
            profile["external_profiles"].append(
                {
                    "provider": "opencorporates",
                    "source_url": company_url,
                    "title": company_name,
                    "excerpt": f"{company_name} ({jurisdiction}/{company_number})",
                }
            )
        details = await _opencorporates_fetch_company(
            client,
            jurisdiction_code=jurisdiction,
            company_number=company_number,
            api_token=oc_token,
        )
        await asyncio.sleep(0.15)
        if not details:
            continue
        officers = details.get("officers") or []
        if isinstance(officers, list):
            for officer_row in officers[:10]:
                officer = (
                    (officer_row or {}).get("officer")
                    if isinstance(officer_row, dict)
                    else None
                )
                if not isinstance(officer, dict):
                    continue
                person_name = str(officer.get("name") or "").strip()
                if len(person_name) < 4:
                    continue
                position = str(officer.get("position") or "").strip() or "officer"
                officer_url = str(officer.get("opencorporates_url") or "").strip() or company_url
                excerpt = f"{person_name} - {position} ({company_name})"
                row = {
                    "name": person_name[:512],
                    "role": position[:128],
                    "confidence": 0.74,
                    "source_provider": "opencorporates",
                    "source_url": officer_url,
                    "evidence_excerpt": excerpt[:1024],
                    "published_at": None,
                    "verification_status": "unverified",
                }
                evidence_rows.append(row)
                lower_pos = position.lower()
                if any(token in lower_pos for token in ("director", "chair", "board")):
                    profile["board_members"].append(row)
                elif any(
                    token in lower_pos
                    for token in ("ceo", "chief", "executive", "president")
                ):
                    profile["executives"].append(row)
                else:
                    profile["executives"].append(row)
    if not oc_companies:
        profile["diagnostics"].append(
            "Ingen OpenCorporates-profil funnet over navnelikhets-terskel."
        )

    for finding in brreg_findings:
        if not isinstance(finding, dict):
            continue
        brreg_name = str(finding.get("name") or "").strip()
        detail_url = str(finding.get("detail_url") or "").strip() or None
        company_site = _normalize_url(str(finding.get("website") or "").strip())
        if not brreg_name:
            continue
        evidence_rows.append(
            {
                "name": brreg_name[:512],
                "role": "official_registry_company_record",
                "confidence": 0.88,
                "source_provider": "brreg",
                "source_url": detail_url,
                "evidence_excerpt": f"Brreg company record for {brreg_name}"[:1024],
                "published_at": None,
                "verification_status": "verified",
            }
        )
        if company_site:
            profile["external_profiles"].append(
                {
                    "provider": "canonical_company_site",
                    "source_url": company_site,
                    "title": brreg_name,
                    "excerpt": "Brreg hjemmeside",
                }
            )

    # Canonical domener brukes for prioritering, men er ikke lenger hardt krav.
    canonical_domains: set[str] = set()
    for finding in website_findings:
        if not isinstance(finding, dict):
            continue
        website_url = _normalize_url(str(finding.get("website") or "").strip())
        if website_url:
            canonical_domains.add(_canonicalize_domain(_domain_of_url(website_url)))
        for page in finding.get("pages") or []:
            if not isinstance(page, dict):
                continue
            page_url = _normalize_url(str(page.get("url") or "").strip())
            if page_url:
                canonical_domains.add(_canonicalize_domain(_domain_of_url(page_url)))

    for candidate in selected_candidates[:4]:
        doc = candidate_docs.get(candidate.qid) or {}
        for raw_url in _extract_claim_strings(doc, "P856", limit=4):
            url = _normalize_url(raw_url)
            if not url:
                continue
            canonical_domains.add(_canonicalize_domain(_domain_of_url(url)))

    for finding in brreg_findings:
        if not isinstance(finding, dict):
            continue
        company_site = _normalize_url(str(finding.get("website") or "").strip())
        if company_site:
            canonical_domains.add(_canonicalize_domain(_domain_of_url(company_site)))

    canonical_domains = {
        domain
        for domain in canonical_domains
        if domain and not _is_registry_or_generic_domain(domain)
    }
    if canonical_domains:
        profile["diagnostics"].append(
            "Canonical domener brukt for websøk: " + ", ".join(sorted(canonical_domains)[:5])
        )
    else:
        profile["diagnostics"].append(
            "Ingen canonical domener funnet; bruker globalt websøk som fallback."
        )

    # Bredere web-søk: domenebasert + global fallback + offisielle sanksjonsdomener.
    if enable_ai_web_search:
        search_queries = _dedupe_keep_order(
            _build_domain_research_queries(seed_name, canonical_domains)
            + _build_research_queries(seed_name)
            + _build_domain_research_queries(seed_name, _OFFICIAL_SANCTIONS_DOMAINS)
        )[: query_profile.max_search_queries]

        metrics = profile.get("web_research")
        if not isinstance(metrics, dict):
            metrics = {}
            profile["web_research"] = metrics
        metrics["queries_planned"] = len(search_queries)

        search_profiles_seen: set[str] = set()
        pages_fetched = 0
        search_pages_with_signal = 0
        for query in search_queries:
            if pages_fetched >= query_profile.max_search_pages_to_fetch:
                break
            metrics["queries_executed"] = int(metrics.get("queries_executed") or 0) + 1
            search_results = await _duckduckgo_html_search(
                client,
                query=query,
                max_results=query_profile.max_search_results_per_query,
            )
            metrics["results_found"] = int(metrics.get("results_found") or 0) + len(search_results)
            for search_row in search_results:
                if pages_fetched >= query_profile.max_search_pages_to_fetch:
                    break
                source_url = str(search_row.get("source_url") or "").strip()
                if not source_url:
                    continue
                source_domain = _canonicalize_domain(_domain_of_url(source_url))
                domain_allowed = (
                    (not canonical_domains)
                    or _domain_matches_allowlist(source_domain, canonical_domains)
                    or _is_official_sanctions_domain(source_domain)
                )
                if not domain_allowed:
                    continue
                source_provider = str(search_row.get("source_provider") or "duckduckgo_search")
                if source_url not in search_profiles_seen:
                    profile["external_profiles"].append(
                        {
                            "provider": source_provider,
                            "source_url": source_url,
                            "title": str(search_row.get("title") or "").strip() or None,
                            "excerpt": f"Query: {query}",
                            "source_tier": _source_tier(source_provider, source_url),
                        }
                    )
                    search_profiles_seen.add(source_url)

                page_text, fetch_error = await _fetch_page_text(client, source_url)
                pages_fetched += 1
                metrics["pages_fetched"] = int(metrics.get("pages_fetched") or 0) + 1
                if page_text is None:
                    metrics["fetch_errors"] = int(metrics.get("fetch_errors") or 0) + 1
                    if fetch_error:
                        profile["diagnostics"].append(
                            f"Web-fetch feil ({_domain_of_url(source_url) or source_url}): {fetch_error[:140]}"
                        )
                    continue
                snippets = _extract_keyword_snippets(
                    page_text,
                    max_snippets=query_profile.max_snippets_per_page,
                )
                if not snippets:
                    parts = re.split(r"(?<=[.!?])\s+", page_text[:_MAX_WEB_SNIPPET_LEN])
                    snippets = [
                        part.strip()[:280]
                        for part in parts
                        if len(part.strip()) >= 40
                    ][: query_profile.max_snippets_per_page]
                if not snippets:
                    continue
                for snippet in snippets:
                    if not _is_snippet_seed_relevant(
                        seed_name=seed_name,
                        source_url=source_url,
                        snippet=snippet,
                    ):
                        continue
                    has_governance = _has_governance_role_cue(snippet)
                    has_sanctions = _has_sanctions_cue(snippet)
                    if not has_governance and not has_sanctions:
                        continue
                    search_pages_with_signal += 1
                    metrics["pages_with_signal"] = int(metrics.get("pages_with_signal") or 0) + 1

                    domain = _domain_of_url(source_url)
                    is_official = _is_official_sanctions_domain(domain)
                    evidence_role = (
                        "web_search_sanctions_signal"
                        if has_sanctions
                        else "web_search_governance_signal"
                    )
                    evidence_conf = 0.82 if is_official and has_sanctions else 0.66
                    evidence_rows.append(
                        {
                            "name": seed_name[:512],
                            "role": evidence_role,
                            "confidence": evidence_conf,
                            "source_provider": source_provider,
                            "source_url": source_url,
                            "evidence_excerpt": snippet[:1024],
                            "published_at": None,
                            "verification_status": "verified" if is_official else "unverified",
                        }
                    )

                    if has_governance:
                        lower = snippet.lower()
                        inferred_role = (
                            "board_member"
                            if re.search(r"\b(board|directors?|chair(?:person)?)\b", lower)
                            else "executive"
                        )
                        for person_name in _extract_person_names_from_signal(
                            snippet,
                            limit=2,
                            seed_name=seed_name,
                            source_url=source_url,
                        ):
                            row = {
                                "name": person_name[:512],
                                "role": inferred_role,
                                "confidence": 0.70 if is_official else 0.66,
                                "source_provider": source_provider,
                                "source_url": source_url,
                                "evidence_excerpt": snippet[:1024],
                                "published_at": None,
                                "verification_status": "verified" if is_official else "unverified",
                            }
                            if inferred_role == "board_member":
                                profile["board_members"].append(row)
                            else:
                                profile["executives"].append(row)

                        for company_name in _extract_company_names_from_signal(
                            snippet,
                            limit=1,
                            seed_name=seed_name,
                            source_url=source_url,
                        ):
                            profile["direct_owners"].append(
                                {
                                    "name": company_name[:512],
                                    "role": "ownership_reference",
                                    "confidence": 0.64 if is_official else 0.60,
                                    "source_provider": source_provider,
                                    "source_url": source_url,
                                    "evidence_excerpt": snippet[:1024],
                                    "published_at": None,
                                    "verification_status": "verified" if is_official else "unverified",
                                }
                            )
        if search_pages_with_signal == 0:
            profile["diagnostics"].append(
                "Websøk fant ingen sider med tydelige governance/sanksjons-signaler."
            )

    web_evidence_rows = [
        row
        for row in evidence_rows
        if str(row.get("source_provider") or "").strip().lower()
        in {"duckduckgo_search", "duckduckgo_proxy_search", "bing_search"}
    ]
    ai_web_payload = await _ai_summarize_web_findings(
        seed_name=seed_name,
        evidence_rows=web_evidence_rows,
    )
    if ai_web_payload:
        summary_text = str(ai_web_payload.get("summary_text") or "").strip()
        if summary_text:
            profile["ai_web_summary"] = summary_text[:1200]
        claims = ai_web_payload.get("key_claims")
        if isinstance(claims, list):
            persisted_claims: list[dict[str, Any]] = []
            for claim in claims[:10]:
                if not isinstance(claim, dict):
                    continue
                claim_text = str(claim.get("claim") or "").strip()
                source_url = _normalize_url(str(claim.get("source_url") or "").strip())
                quote = str(claim.get("quote") or "").strip()
                try:
                    confidence = float(claim.get("confidence"))
                except (TypeError, ValueError):
                    confidence = 0.6
                if len(claim_text) < 8 or len(quote) < 12 or not source_url:
                    continue
                persisted_claims.append(
                    {
                        "claim": claim_text[:512],
                        "source_url": source_url,
                        "quote": quote[:1024],
                        "confidence": round(max(0.0, min(1.0, confidence)), 4),
                    }
                )
            profile["ai_web_claims"] = persisted_claims
            for row in persisted_claims[:8]:
                evidence_rows.append(
                    {
                        "name": seed_name[:512],
                        "role": "ai_web_claim",
                        "confidence": float(row.get("confidence") or 0.6),
                        "source_provider": "ai_synthesis",
                        "source_url": row.get("source_url"),
                        "evidence_excerpt": row.get("quote"),
                        "published_at": None,
                        "verification_status": "unverified",
                    }
                )

    if enable_ai_entity_research:
        ai_payload = await _ai_extract_ownership_profile(
            seed_name=seed_name,
            evidence_rows=evidence_rows,
        )
        ai_profile = _extract_profile_rows_from_ai(ai_payload, seed_name=seed_name)
        if ai_profile.get("ultimate_parent") and profile.get("ultimate_parent") is None:
            profile["ultimate_parent"] = ai_profile["ultimate_parent"]
        profile["direct_owners"].extend(ai_profile.get("direct_owners") or [])
        profile["beneficial_owners"].extend(ai_profile.get("beneficial_owners") or [])
        profile["board_members"].extend(ai_profile.get("board_members") or [])
        profile["executives"].extend(ai_profile.get("executives") or [])
        if not ai_payload:
            profile["diagnostics"].append("AI-ekstraksjon ga ingen strukturert respons.")

    profile["direct_owners"] = _dedupe_profile_rows(profile.get("direct_owners") or [])
    profile["beneficial_owners"] = _dedupe_profile_rows(profile.get("beneficial_owners") or [])
    profile["board_members"] = _dedupe_profile_rows(profile.get("board_members") or [])
    profile["executives"] = _dedupe_profile_rows(profile.get("executives") or [])
    if isinstance(profile.get("ultimate_parent"), dict):
        parent_rows = _dedupe_profile_rows([profile["ultimate_parent"]])
        profile["ultimate_parent"] = parent_rows[0] if parent_rows else None

    profile["source_evidence"] = _dedupe_profile_rows(evidence_rows)[:60]

    seed_country_code = str(seed_country or "").strip().upper()
    country_rows: list[dict[str, Any]] = []
    for row in [
        profile.get("ultimate_parent"),
        *profile.get("direct_owners", []),
        *profile.get("beneficial_owners", []),
        *profile.get("board_members", []),
        *profile.get("executives", []),
    ]:
        if not isinstance(row, dict):
            continue
        text = f"{row.get('name', '')} {row.get('evidence_excerpt', '')}".lower()
        for risk_name in _RISK_COUNTRY_NAMES:
            if risk_name in text:
                country_rows.append(
                    {
                        "country": risk_name,
                        "reason": "mentioned in ownership/management evidence",
                        "source": row.get("source_provider"),
                    }
                )
                break
    if seed_country_code and seed_country_code in _RISK_COUNTRY_CODES:
        country_rows.append(
            {
                "country": seed_country_code,
                "reason": "seed entity country on high-risk list",
                "source": "entity_metadata",
            }
        )
    profile["risk_country_signals"] = list(
        {
            (str(row.get("country")), str(row.get("source"))): row
            for row in country_rows
            if isinstance(row, dict)
        }.values()
    )
    if not profile["source_evidence"]:
        profile["diagnostics"].append("Ingen evidenslinjer samlet fra tilgjengelige kilder.")

    return profile


def _best_name_match(
    candidate_name: str,
    records: list[dict[str, Any]],
    *,
    name_key: str,
) -> tuple[dict[str, Any] | None, float]:
    best_row: dict[str, Any] | None = None
    best_score = 0.0
    for row in records:
        record_name = str(row.get(name_key) or "").strip()
        if not record_name:
            continue
        score = _name_similarity(candidate_name, record_name)
        if score > best_score:
            best_score = score
            best_row = row
    return best_row, best_score


async def _match_external_sanctions(
    session: AsyncSession,
    *,
    names: list[dict[str, str]],
    enable_uk_sanctions: bool,
    enable_world_bank_debarred: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    result = await session.execute(
        select(ExternalWatchlistEntry).where(
            ExternalWatchlistEntry.source.in_(
                [SOURCE_UK_SANCTIONS, SOURCE_WORLD_BANK_DEBARRED]
            )
        )
    )
    entries = result.scalars().all()
    uk_records = [
        {
            "unique_id": row.external_id,
            "name": row.name,
            "sanctions_imposed": row.sanctions_type,
        }
        for row in entries
        if row.source == SOURCE_UK_SANCTIONS
    ]
    wb_records = [
        {
            "supplier_id": row.external_id,
            "name": row.name,
            "country": row.country,
            "debar_type": row.sanctions_type,
        }
        for row in entries
        if row.source == SOURCE_WORLD_BANK_DEBARRED
    ]
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for row in names:
        candidate_name = str(row.get("name") or "").strip()
        if len(candidate_name) < 4:
            continue
        relation = str(row.get("relation") or "external_name")
        source_qid = str(row.get("source_qid") or "")

        uk_match, uk_score = _best_name_match(candidate_name, uk_records, name_key="name")
        if enable_uk_sanctions and uk_match and uk_score >= 0.84:
            key = ("UK_SANCTIONS", candidate_name.lower(), str(uk_match.get("unique_id") or ""))
            if key not in seen:
                seen.add(key)
                hits.append(
                    {
                        "target_name": candidate_name,
                        "target_type": str(row.get("target_type") or "unknown"),
                        "relation": relation,
                        "source_qid": source_qid,
                        "dataset": "UK_SANCTIONS",
                        "score": round(uk_score, 4),
                        "matched_name": uk_match.get("name"),
                        "dataset_entity_id": uk_match.get("unique_id"),
                        "validation_reason": "uk_sanctions_csv_fuzzy_match",
                        "source_provider": SOURCE_UK_SANCTIONS,
                        "raw": uk_match,
                    }
                )

        wb_match, wb_score = _best_name_match(candidate_name, wb_records, name_key="name")
        if enable_world_bank_debarred and wb_match and wb_score >= 0.86:
            key = (
                "WORLD_BANK_DEBARRED",
                candidate_name.lower(),
                str(wb_match.get("supplier_id") or ""),
            )
            if key not in seen:
                seen.add(key)
                hits.append(
                    {
                        "target_name": candidate_name,
                        "target_type": str(row.get("target_type") or "unknown"),
                        "relation": relation,
                        "source_qid": source_qid,
                        "dataset": "WORLD_BANK_DEBARRED",
                        "score": round(wb_score, 4),
                        "matched_name": wb_match.get("name"),
                        "dataset_entity_id": wb_match.get("supplier_id"),
                        "validation_reason": "world_bank_debarred_fuzzy_match",
                        "source_provider": SOURCE_WORLD_BANK_DEBARRED,
                        "raw": wb_match,
                    }
                )

    hits.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    health_rows = await list_external_source_health(session, include_brreg_probe=False)
    health_by_source = {str(row.get("source") or ""): row for row in health_rows}
    sources = []
    for source_name, enabled in (
        (SOURCE_UK_SANCTIONS, enable_uk_sanctions),
        (SOURCE_WORLD_BANK_DEBARRED, enable_world_bank_debarred),
    ):
        row = health_by_source.get(source_name) or {}
        sources.append(
            {
                "provider": source_name,
                "source_url": (
                    _UK_SANCTIONS_CSV_URL
                    if source_name == SOURCE_UK_SANCTIONS
                    else _WORLD_BANK_DEBARRED_API_URL
                ),
                "enabled": enabled,
                "status": "disabled" if not enabled else str(row.get("status") or "unknown"),
                "error": str(row.get("error_message") or "") or None,
                "record_count": row.get("entry_count"),
                "fetched_at": (
                    row.get("last_updated").isoformat()
                    if isinstance(row.get("last_updated"), datetime)
                    else None
                ),
            }
        )
    return hits, sources


async def _search_brreg_companies(
    client: httpx.AsyncClient,
    *,
    names: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    associations: list[dict[str, Any]] = []
    seen_org: set[str] = set()
    seen_assoc: set[tuple[str, str]] = set()

    for name in names:
        query_name = name.strip()
        if len(query_name) < 4:
            continue
        try:
            response = await client.get(
                _BRREG_ENHETER_API_URL,
                params={"navn": query_name, "size": 2},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning(
                "extended_screen_brreg_search_failed",
                query_name=query_name,
                error=str(exc),
            )
            continue
        entities = ((payload or {}).get("_embedded") or {}).get("enheter") or []
        if not isinstance(entities, list):
            continue

        for entity in entities:
            if not isinstance(entity, dict):
                continue
            orgnr = str(entity.get("organisasjonsnummer") or "").strip()
            company_name = str(entity.get("navn") or "").strip()
            if not orgnr or not company_name:
                continue
            if _name_similarity(query_name, company_name) < 0.86:
                continue
            if orgnr in seen_org:
                continue
            seen_org.add(orgnr)

            detail_url = f"{_BRREG_ENHETER_API_URL}/{orgnr}"
            roles_url = f"{_BRREG_ENHETER_API_URL}/{orgnr}/roller"
            detail_country = (
                ((entity.get("forretningsadresse") or {}).get("landkode") or "")
                if isinstance(entity.get("forretningsadresse"), dict)
                else ""
            )
            finding = {
                "orgnr": orgnr,
                "name": company_name,
                "detail_url": detail_url,
                "roles_url": roles_url,
                "website": str(entity.get("hjemmeside") or "").strip() or None,
                "country_code": detail_country or None,
                "queried_name": query_name,
            }
            findings.append(finding)

            try:
                roles_resp = await client.get(roles_url)
                roles_resp.raise_for_status()
                roles_payload = roles_resp.json()
            except Exception:
                roles_payload = {}

            role_groups = (roles_payload or {}).get("rollegrupper") or []
            if not isinstance(role_groups, list):
                continue

            for group in role_groups:
                if not isinstance(group, dict):
                    continue
                roles = group.get("roller") or []
                if not isinstance(roles, list):
                    continue
                for role in roles:
                    if not isinstance(role, dict):
                        continue
                    person = role.get("person") or {}
                    if not isinstance(person, dict):
                        continue
                    navn_obj = person.get("navn") or {}
                    if not isinstance(navn_obj, dict):
                        navn_obj = {}
                    person_name = str(navn_obj.get("sammensattnavn") or "").strip()
                    if not person_name:
                        fornavn = str(navn_obj.get("fornavn") or "").strip()
                        mellomnavn = str(navn_obj.get("mellomnavn") or "").strip()
                        etternavn = str(navn_obj.get("etternavn") or "").strip()
                        person_name = " ".join(
                            part for part in [fornavn, mellomnavn, etternavn] if part
                        ).strip()
                    if len(person_name) < 4:
                        continue
                    assoc_key = (orgnr, person_name.lower())
                    if assoc_key in seen_assoc:
                        continue
                    seen_assoc.add(assoc_key)
                    role_type = str((role.get("type") or {}).get("kode") or "").strip()
                    associations.append(
                        {
                            "source": "brreg",
                            "source_qid": f"BRREG:{orgnr}",
                            "source_label": company_name,
                            "source_type": "company",
                            "source_url": roles_url,
                            "relation": "brreg_role_holder",
                            "edge_confidence": 0.93,
                            "target": {
                                "qid": f"BRREG_PERSON:{orgnr}:{person_name}",
                                "name": person_name,
                                "description": (
                                    f"Role code: {role_type}" if role_type else "Brreg role"
                                ),
                                "type": "person",
                            },
                        }
                    )

    return findings, associations


def _risk_countries_from_associations(associations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for assoc in associations:
        relation = str(assoc.get("relation") or "")
        target = assoc.get("target") or {}
        name = str(target.get("name") or "")

        if relation in {"country", "country_of_citizenship"}:
            candidates = [name, str(target.get("description") or "")]
            codes = _iso2_candidates_from_text(" ".join(candidates))
            for code in codes:
                if code in _RISK_COUNTRY_CODES:
                    key = (relation, code)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        {
                            "relation": relation,
                            "country": code,
                            "reason": "country on high-risk watchlist",
                            "source": "wikidata",
                        }
                    )

            lowered = name.lower()
            for risk_name in _RISK_COUNTRY_NAMES:
                if risk_name in lowered:
                    key = (relation, risk_name)
                    if key in seen:
                        continue
                    seen.add(key)
                    findings.append(
                        {
                            "relation": relation,
                            "country": name,
                            "reason": "country name on high-risk watchlist",
                            "source": "wikidata",
                        }
                    )

    return findings


def _risk_countries_from_site(findings: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    signals = findings.get("owner_board_management_signals") or []
    if not isinstance(signals, list):
        return out

    for signal in signals:
        text = str(signal).lower()
        for risk_name in _RISK_COUNTRY_NAMES:
            if risk_name in text:
                out.append(
                    {
                        "relation": "website_context",
                        "country": risk_name,
                        "reason": "mentioned in company website management/ownership context",
                        "source": "website",
                        "signal": str(signal)[:260],
                    }
                )
                break

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in out:
        key = (str(row.get("relation")), str(row.get("country")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    return deduped


async def _sanctions_check_associations(
    associations: list[dict[str, Any]],
    profile: _Profile,
) -> list[dict[str, Any]]:
    settings = get_settings()
    min_score = float(settings.screening_match_threshold)

    yente = get_yente_client()
    if not await yente.is_healthy():
        return []

    checks: list[dict[str, Any]] = []
    for assoc in associations:
        if float(assoc.get("edge_confidence") or 0.0) < profile.min_edge_confidence:
            continue
        if str(assoc.get("relation") or "") in {
            "country",
            "country_of_citizenship",
            "headquarters_location",
        }:
            continue

        target = assoc.get("target") or {}
        target_type = str(target.get("type") or "unknown")
        if target_type not in {"person", "company"}:
            continue
        target_name = str(target.get("name") or "").strip()
        if len(target_name) < 4:
            continue
        checks.append(assoc)
    checks = checks[: profile.max_sanctions_checks]

    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for assoc in checks:
        target = assoc.get("target") or {}
        target_name = str(target.get("name") or "").strip()
        if not target_name:
            continue

        target_type = str(target.get("type") or "unknown")
        entity_type = "person" if target_type == "person" else "company"

        matches = await yente.match_entity(
            name=target_name,
            entity_type=entity_type,
            country=None,
        )

        for match in matches:
            if match.score < min_score:
                continue
            accepted, reason = _is_plausible_sanctions_hit(
                target_name=target_name,
                matched_name=match.matched_name,
                match_score=float(match.score),
            )
            if not accepted:
                logger.info(
                    "extended_screen_skip_sanction_hit",
                    target_name=target_name,
                    matched_name=match.matched_name,
                    score=float(match.score),
                    reason=reason,
                )
                continue

            key = (target_name.lower(), match.dataset, str(match.matched_name or "").lower())
            if key in seen:
                continue
            seen.add(key)

            hits.append(
                {
                    "target_name": target_name,
                    "target_type": target_type,
                    "relation": assoc.get("relation"),
                    "source_qid": assoc.get("source_qid"),
                    "dataset": match.dataset,
                    "score": round(float(match.score), 4),
                    "matched_name": match.matched_name,
                    "dataset_entity_id": match.entity_id,
                    "validation_reason": reason,
                }
            )

    hits.sort(key=lambda item: item["score"], reverse=True)
    return hits


async def _sanctions_check_seed_entity(
    *,
    seed_name: str,
    seed_entity_type: str,
    seed_country: str | None,
) -> list[dict[str, Any]]:
    settings = get_settings()
    min_score = float(settings.screening_match_threshold)
    yente = get_yente_client()
    if not await yente.is_healthy():
        return []

    entity_type = "person" if seed_entity_type == "person" else "company"
    matches = await yente.match_entity(
        name=seed_name,
        entity_type=entity_type,
        country=seed_country,
    )
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for match in matches:
        score = float(match.score)
        if score < min_score:
            continue
        matched_name = str(match.matched_name or "").strip()
        key = (str(match.dataset), matched_name.lower())
        if key in seen:
            continue
        seen.add(key)
        hits.append(
            {
                "target_name": seed_name,
                "target_type": seed_entity_type,
                "relation": "seed_direct",
                "source_qid": "",
                "dataset": match.dataset,
                "score": round(score, 4),
                "matched_name": matched_name or seed_name,
                "dataset_entity_id": match.entity_id,
                "validation_reason": "direct_seed_entity_match",
                "source_provider": "yente",
            }
        )
    hits.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return hits


async def _screen_ownership_profile_entities(
    session: AsyncSession,
    *,
    ownership_profile: dict[str, Any],
    enable_uk_sanctions: bool,
    enable_world_bank_debarred: bool,
) -> list[dict[str, Any]]:
    settings = get_settings()
    min_score = float(settings.screening_match_threshold)
    rows: list[dict[str, str]] = []

    def _append_people(items: Any, relation: str) -> None:
        if not isinstance(items, list):
            return
        for row in items:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            if len(name) < 4:
                continue
            rows.append(
                {
                    "name": name,
                    "relation": relation,
                    "target_type": "person",
                    "source_qid": "",
                }
            )

    def _append_companies(items: Any, relation: str) -> None:
        if not isinstance(items, list):
            return
        for row in items:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            if len(name) < 4:
                continue
            rows.append(
                {
                    "name": name,
                    "relation": relation,
                    "target_type": "company",
                    "source_qid": "",
                }
            )

    parent = ownership_profile.get("ultimate_parent")
    if isinstance(parent, dict):
        name = str(parent.get("name") or "").strip()
        if len(name) >= 4:
            rows.append(
                {
                    "name": name,
                    "relation": "ultimate_parent",
                    "target_type": "company",
                    "source_qid": "",
                }
            )
    _append_companies(ownership_profile.get("direct_owners"), "direct_owner")
    _append_companies(ownership_profile.get("beneficial_owners"), "beneficial_owner")
    _append_people(ownership_profile.get("board_members"), "board_member")
    _append_people(ownership_profile.get("executives"), "executive")

    deduped_rows = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("name") or "").lower(),
            str(row.get("relation") or ""),
            str(row.get("target_type") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped_rows.append(row)

    yente = get_yente_client()
    yente_hits: list[dict[str, Any]] = []
    if await yente.is_healthy():
        for row in deduped_rows[:30]:
            name = str(row.get("name") or "").strip()
            entity_type = "person" if row.get("target_type") == "person" else "company"
            matches = await yente.match_entity(name=name, entity_type=entity_type, country=None)
            for match in matches:
                if float(match.score) < min_score:
                    continue
                accepted, reason = _is_plausible_sanctions_hit(
                    target_name=name,
                    matched_name=match.matched_name,
                    match_score=float(match.score),
                )
                if not accepted:
                    continue
                yente_hits.append(
                    {
                        "target_name": name,
                        "target_type": str(row.get("target_type") or "unknown"),
                        "relation": str(row.get("relation") or "ownership_relation"),
                        "source_qid": "",
                        "dataset": match.dataset,
                        "score": round(float(match.score), 4),
                        "matched_name": match.matched_name,
                        "dataset_entity_id": match.entity_id,
                        "validation_reason": reason,
                        "source_provider": "ownership_profile",
                    }
                )

    external_hits: list[dict[str, Any]] = []
    company_rows = [row for row in deduped_rows if row.get("target_type") == "company"]
    if company_rows:
        external_hits, _ = await _match_external_sanctions(
            session,
            names=company_rows,
            enable_uk_sanctions=enable_uk_sanctions,
            enable_world_bank_debarred=enable_world_bank_debarred,
        )
    all_hits = yente_hits + external_hits
    all_hits.sort(key=lambda item: float(item.get("score") or 0.0), reverse=True)
    return all_hits


def _summary_from_payload(payload: dict[str, Any]) -> tuple[str, str]:
    settings = get_settings()
    confirmed_threshold = float(settings.screening_confirmed_threshold)
    potential_threshold = float(settings.screening_match_threshold)

    sanctions_hits = payload.get("sanctions_hits") or []
    country_exposure = payload.get("country_exposure") or []
    website_findings = payload.get("website_findings") or []
    ownership = payload.get("ownership_management") or {}
    max_score = 0.0

    for hit in sanctions_hits:
        try:
            raw_score = float(hit.get("score") or 0.0)
            weighted = _weighted_hit_score(hit, raw_score=raw_score)
            max_score = max(max_score, weighted)
        except (TypeError, ValueError):
            continue

    if max_score >= confirmed_threshold:
        return (
            "high",
            (
                "Hoey risiko: sterk kobling mellom assosiert entitet og sanksjonsliste "
                f"(vektet topp-score {max_score:.2f})."
            ),
        )
    if max_score >= potential_threshold:
        return (
            "medium",
            (
                "Moderat risiko: minst en assosiert entitet ga potensielt sanksjonstreff "
                f"(vektet topp-score {max_score:.2f})."
            ),
        )

    if country_exposure:
        return (
            "medium",
            "Moderat risiko: funnet eksponering mot land med hoy risiko i nettverkskontekst.",
        )

    if website_findings:
        return (
            "low",
            (
                "Lav risiko: ingen sanksjonstreff, men nettside ga "
                "styrings/eierskapssignaler for manuell vurdering."
            ),
        )

    ownership_count = 0
    if isinstance(ownership, dict):
        ownership_count = (
            len(ownership.get("direct_owners") or [])
            + len(ownership.get("beneficial_owners") or [])
            + len(ownership.get("board_members") or [])
            + len(ownership.get("executives") or [])
            + (1 if isinstance(ownership.get("ultimate_parent"), dict) else 0)
        )
    if ownership_count > 0:
        return (
            "low",
            (
                "Lav risiko: eierskap/ledelse ble kartlagt uten tydelige sanksjonstreff. "
                "Manuell vurdering anbefales for verifisering."
            ),
        )

    return (
        "low",
        "Lav risiko: ingen tydelige sanksjonstreff eller hoyrisiko-eksponering i gratis kilder.",
    )


def _weighted_hit_score(hit: dict[str, Any], *, raw_score: float) -> float:
    settings = get_settings()
    dataset = str(hit.get("dataset") or "").upper()
    if dataset == "UK_SANCTIONS":
        weight = float(settings.source_weight_uk_sanctions)
    elif dataset == "WORLD_BANK_DEBARRED":
        weight = float(settings.source_weight_world_bank_debarred)
    else:
        weight = float(settings.source_weight_yente)
    score = raw_score * max(0.0, min(1.5, weight))
    return round(max(0.0, min(1.0, score)), 4)


def _claim_type_from_relation(relation: str) -> str:
    mapping = {
        "parent_organization": "parent_organization",
        "owned_by": "ownership_link",
        "founded_by": "founder_link",
        "chief_executive_officer": "executive_link",
        "chairperson": "board_link",
        "board_member": "board_link",
        "country": "country_link",
        "country_of_citizenship": "country_link",
        "headquarters_location": "location_link",
        "employer": "employment_link",
        "member_of": "membership_link",
    }
    return mapping.get(relation, "association_link")


def _confidence_value(value: Any) -> float | None:
    return float(value) if isinstance(value, float | int) else None


def _verification_from_confidence(value: Any) -> str:
    conf = float(value) if isinstance(value, float | int) else 0.0
    return "verified" if conf >= 0.95 else "unverified"


_EXCLUSIVE_CLAIM_TYPES = {
    "legal_entity_identifier",
    "jurisdiction_country",
}


def _as_float(value: Any) -> float | None:
    if isinstance(value, float | int):
        return float(value)
    return None


def _claim_norm(value: str) -> str:
    return _normalize_text(value)


def _extract_person_names_from_signal(
    signal: str,
    *,
    limit: int = 3,
    seed_name: str | None = None,
    source_url: str | None = None,
) -> list[str]:
    if seed_name and not _is_snippet_seed_relevant(
        seed_name=seed_name,
        source_url=source_url,
        snippet=signal,
    ):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for match in _PERSON_NAME_PATTERN.finditer(signal):
        candidate = match.group(0).strip()
        if len(candidate) < 5:
            continue
        if not _has_person_role_context(signal, match.start(), match.end()):
            continue
        if not _is_plausible_person_name(candidate):
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(candidate)
        if len(names) >= limit:
            break
    return names


def _extract_company_names_from_signal(
    signal: str,
    *,
    limit: int = 3,
    seed_name: str | None = None,
    source_url: str | None = None,
) -> list[str]:
    if seed_name and not _is_snippet_seed_relevant(
        seed_name=seed_name,
        source_url=source_url,
        snippet=signal,
    ):
        return []
    companies: list[str] = []
    seen: set[str] = set()
    pattern = re.compile(
        r"\b([A-Z][A-Za-z0-9&.\- ]{1,70}?\s"
        r"(?:Inc|Ltd|LLC|PLC|GmbH|ASA|AS|AG|BV|S\.A\.|S\.R\.L\.))\b"
    )
    for match in pattern.findall(signal):
        candidate = str(match).strip(" ,.;:")
        if len(candidate) < 4:
            continue
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        companies.append(candidate)
        if len(companies) >= limit:
            break
    return companies


def _resolver_base_payload(claim: ExtendedScreenClaim) -> dict[str, Any]:
    existing = claim.raw_payload if isinstance(claim.raw_payload, dict) else {}
    return dict(existing)


def _resolve_claim_verification(
    claims: list[ExtendedScreenClaim],
    *,
    selected_candidate_qids: set[str],
    sanctions_hit_names: list[tuple[str, float]],
) -> None:
    by_fingerprint: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_subject_type: dict[tuple[str, str], set[str]] = {}

    for claim in claims:
        subject_key = _claim_norm(claim.claim_subject)
        object_key = _claim_norm(claim.claim_object)
        fingerprint = (claim.claim_type, subject_key, object_key)
        slot = by_fingerprint.setdefault(
            fingerprint,
            {"providers": set(), "max_confidence": None},
        )
        slot["providers"].add(claim.source_provider)
        conf = _as_float(claim.confidence)
        if conf is not None and (
            slot["max_confidence"] is None or conf > float(slot["max_confidence"])
        ):
            slot["max_confidence"] = conf

        if claim.claim_type in _EXCLUSIVE_CLAIM_TYPES:
            key = (subject_key, claim.claim_type)
            bucket = by_subject_type.setdefault(key, set())
            bucket.add(object_key)

    conflicting_keys: set[tuple[str, str, str]] = set()
    for (subject_key, claim_type), object_keys in by_subject_type.items():
        if len(object_keys) <= 1:
            continue
        for object_key in object_keys:
            conflicting_keys.add((claim_type, subject_key, object_key))

    threshold = float(get_settings().screening_match_threshold)

    for claim in claims:
        subject_key = _claim_norm(claim.claim_subject)
        object_key = _claim_norm(claim.claim_object)
        fingerprint = (claim.claim_type, subject_key, object_key)
        support = by_fingerprint.get(fingerprint) or {}
        providers = sorted(str(p) for p in (support.get("providers") or set()))
        conf = _as_float(claim.confidence)
        reason_code = "single_source_signal"
        status = "unverified"
        source_tier = _source_tier(claim.source_provider, claim.source_url)

        if fingerprint in conflicting_keys:
            status = "conflicting"
            reason_code = "multiple_values_same_claim_type"
        elif len(providers) >= 2:
            status = "verified"
            reason_code = "cross_source_corroborated"
        elif source_tier == "official":
            status = "verified"
            reason_code = "official_source_evidence"
        elif claim.source_provider == "gleif" and (conf or 0.0) >= 0.90:
            status = "verified"
            reason_code = "authoritative_registry_match"
        else:
            source_qid = ""
            if isinstance(claim.raw_payload, dict):
                source_qid = str(claim.raw_payload.get("source_qid") or "").strip()
            if source_qid and source_qid in selected_candidate_qids and (conf or 0.0) >= 0.86:
                status = "verified"
                reason_code = "selected_wikidata_candidate_high_confidence"

        if status != "conflicting":
            for hit_name, hit_score in sanctions_hit_names:
                similarity = _name_similarity(claim.claim_object, hit_name)
                if similarity >= 0.90 and hit_score >= threshold:
                    status = "verified"
                    reason_code = "sanctions_match_correlated"
                    break

        claim.verification_status = status
        claim.raw_payload = {
            **_resolver_base_payload(claim),
            "resolver": {
                "reason_code": reason_code,
                "support_provider_count": len(providers),
                "support_providers": providers,
                "subject_normalized": subject_key,
                "object_normalized": object_key,
                "selected_candidate_used": (
                    reason_code == "selected_wikidata_candidate_high_confidence"
                ),
                "source_tier": source_tier,
            },
        }


def _build_phase1_sources(
    *,
    run: ExtendedScreenRun,
    payload: dict[str, Any],
) -> list[ExtendedScreenSource]:
    rows: list[ExtendedScreenSource] = []
    seen: set[tuple[str, str]] = set()

    for candidate in payload.get("wikidata_candidates") or []:
        if not isinstance(candidate, dict):
            continue
        qid = str(candidate.get("qid") or "").strip()
        if not qid:
            continue
        url = f"https://www.wikidata.org/wiki/{qid}"
        key = ("wikidata", url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            ExtendedScreenSource(
                run_id=run.id,
                invoice_id=run.invoice_id,
                entity_id=run.entity_id,
                provider="wikidata",
                source_url=url,
                source_title=str(candidate.get("label") or qid)[:512],
                source_domain=_domain_of_url(url),
                raw_payload=candidate,
            )
        )

    for match in payload.get("gleif_matches") or []:
        if not isinstance(match, dict):
            continue
        url = str(match.get("source_url") or "").strip()
        if not url:
            continue
        key = ("gleif", url)
        if key in seen:
            continue
        seen.add(key)
        title = str(match.get("legal_name") or match.get("lei") or "GLEIF record")
        rows.append(
            ExtendedScreenSource(
                run_id=run.id,
                invoice_id=run.invoice_id,
                entity_id=run.entity_id,
                provider="gleif",
                source_url=url,
                source_title=title[:512],
                source_domain=_domain_of_url(url),
                raw_payload=match,
            )
        )

    for finding in payload.get("website_findings") or []:
        if not isinstance(finding, dict):
            continue
        pages = finding.get("pages") or []
        if not isinstance(pages, list):
            continue
        for page in pages:
            if not isinstance(page, dict):
                continue
            url = str(page.get("url") or "").strip()
            if not url:
                continue
            key = ("company_website", url)
            if key in seen:
                continue
            seen.add(key)
            title = f"Company website page ({_domain_of_url(url) or 'unknown'})"
            rows.append(
                ExtendedScreenSource(
                    run_id=run.id,
                    invoice_id=run.invoice_id,
                    entity_id=run.entity_id,
                    provider="company_website",
                    source_url=url,
                    source_title=title[:512],
                    source_domain=_domain_of_url(url),
                    raw_payload=page,
                )
            )

    for finding in payload.get("brreg_findings") or []:
        if not isinstance(finding, dict):
            continue
        url = str(finding.get("detail_url") or "").strip()
        if not url:
            continue
        key = ("brreg", url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            ExtendedScreenSource(
                run_id=run.id,
                invoice_id=run.invoice_id,
                entity_id=run.entity_id,
                provider="brreg",
                source_url=url,
                source_title=str(finding.get("name") or "Brreg company")[:512],
                source_domain=_domain_of_url(url),
                raw_payload=finding,
            )
        )

    for source_row in payload.get("external_source_status") or []:
        if not isinstance(source_row, dict):
            continue
        url = str(source_row.get("source_url") or "").strip()
        provider = str(source_row.get("provider") or "").strip()
        if not provider or not url:
            continue
        key = (provider, url)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            ExtendedScreenSource(
                run_id=run.id,
                invoice_id=run.invoice_id,
                entity_id=run.entity_id,
                provider=provider[:32],
                source_url=url,
                source_title=f"{provider} dataset"[:512],
                source_domain=_domain_of_url(url),
                raw_payload=source_row,
            )
        )

    ownership = payload.get("ownership_management") or {}
    if isinstance(ownership, dict):
        for row in ownership.get("external_profiles") or []:
            if not isinstance(row, dict):
                continue
            url = str(row.get("source_url") or "").strip()
            provider = str(row.get("provider") or "external_profile").strip() or "external_profile"
            if not url:
                continue
            key = (provider, url)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                ExtendedScreenSource(
                    run_id=run.id,
                    invoice_id=run.invoice_id,
                    entity_id=run.entity_id,
                    provider=provider[:32],
                    source_url=url,
                    source_title=str(row.get("title") or provider)[:512],
                    source_domain=_domain_of_url(url),
                    raw_payload=row,
                )
            )
        for row in ownership.get("source_evidence") or []:
            if not isinstance(row, dict):
                continue
            url = str(row.get("source_url") or "").strip()
            provider = (
                str(row.get("source_provider") or "ownership_evidence").strip()
                or "ownership_evidence"
            )
            if not url:
                continue
            key = (provider, url)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                ExtendedScreenSource(
                    run_id=run.id,
                    invoice_id=run.invoice_id,
                    entity_id=run.entity_id,
                    provider=provider[:32],
                    source_url=url,
                    source_title=f"{provider} evidence"[:512],
                    source_domain=_domain_of_url(url),
                    raw_payload=row,
                )
            )

    for row in rows:
        existing = row.raw_payload if isinstance(row.raw_payload, dict) else {}
        row.raw_payload = {
            **existing,
            "source_tier": _source_tier(row.provider, row.source_url),
        }

    return rows


def _build_phase1_claims(
    *,
    run: ExtendedScreenRun,
    payload: dict[str, Any],
    seed_name: str,
) -> list[ExtendedScreenClaim]:
    claims: list[ExtendedScreenClaim] = []
    selected_candidate_qids = {
        str(row.get("qid") or "").strip()
        for row in (payload.get("wikidata_candidates") or [])
        if isinstance(row, dict) and bool(row.get("selected"))
    }
    sanctions_hit_names: list[tuple[str, float]] = []
    for hit in payload.get("sanctions_hits") or []:
        if not isinstance(hit, dict):
            continue
        target_name = str(hit.get("target_name") or "").strip()
        if not target_name:
            continue
        try:
            score = float(hit.get("score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        sanctions_hit_names.append((target_name, score))

    for assoc in payload.get("associations") or []:
        if not isinstance(assoc, dict):
            continue
        target = assoc.get("target") or {}
        if not isinstance(target, dict):
            continue
        relation = str(assoc.get("relation") or "related_to")
        target_name = str(target.get("name") or "").strip()
        if not target_name:
            continue
        source_qid = str(assoc.get("source_qid") or "").strip()
        assoc_source = str(assoc.get("source") or "wikidata").strip().lower()
        source_url = str(assoc.get("source_url") or "").strip() or None
        if not source_url and source_qid:
            if assoc_source == "wikidata":
                source_url = f"https://www.wikidata.org/wiki/{source_qid}"
            elif source_qid.startswith("BRREG:"):
                source_url = f"{_BRREG_ENHETER_API_URL}/{source_qid.replace('BRREG:', '')}"
        confidence = assoc.get("edge_confidence")
        claims.append(
            ExtendedScreenClaim(
                run_id=run.id,
                invoice_id=run.invoice_id,
                entity_id=run.entity_id,
                claim_type=_claim_type_from_relation(relation),
                claim_subject=seed_name[:512],
                claim_object=target_name[:1024],
                confidence=_confidence_value(confidence),
                verification_status="unverified",
                source_provider=(assoc_source or "wikidata")[:32],
                source_url=source_url,
                quoted_text=f"{seed_name} --{relation}--> {target_name}"[:2048],
                raw_payload=assoc,
            )
        )

    for match in payload.get("gleif_matches") or []:
        if not isinstance(match, dict):
            continue
        legal_name = str(match.get("legal_name") or "").strip()
        lei = str(match.get("lei") or "").strip()
        if not legal_name or not lei:
            continue
        confidence = match.get("confidence")
        source_url = str(match.get("source_url") or "").strip() or None
        claims.append(
            ExtendedScreenClaim(
                run_id=run.id,
                invoice_id=run.invoice_id,
                entity_id=run.entity_id,
                claim_type="legal_entity_identifier",
                claim_subject=legal_name[:512],
                claim_object=lei[:1024],
                confidence=_confidence_value(confidence),
                verification_status=_verification_from_confidence(confidence),
                source_provider="gleif",
                source_url=source_url,
                quoted_text=f"GLEIF: {legal_name} has LEI {lei}"[:2048],
                raw_payload=match,
            )
        )
        jurisdiction = str(match.get("jurisdiction") or "").strip()
        if jurisdiction:
            claims.append(
                ExtendedScreenClaim(
                    run_id=run.id,
                    invoice_id=run.invoice_id,
                    entity_id=run.entity_id,
                    claim_type="jurisdiction_country",
                    claim_subject=legal_name[:512],
                    claim_object=jurisdiction[:1024],
                    confidence=_confidence_value(confidence),
                    verification_status=_verification_from_confidence(confidence),
                    source_provider="gleif",
                    source_url=source_url,
                    quoted_text=f"GLEIF jurisdiction: {jurisdiction}"[:2048],
                    raw_payload=match,
                )
            )

    for finding in payload.get("website_findings") or []:
        if not isinstance(finding, dict):
            continue
        website_url = str(finding.get("website") or "").strip() or None
        signals = finding.get("owner_board_management_signals") or []
        if not isinstance(signals, list):
            continue
        for signal in signals:
            signal_text = str(signal).strip()
            if len(signal_text) < 24:
                continue
            signal_conf = 0.66
            claims.append(
                ExtendedScreenClaim(
                    run_id=run.id,
                    invoice_id=run.invoice_id,
                    entity_id=run.entity_id,
                    claim_type="website_governance_signal",
                    claim_subject=seed_name[:512],
                    claim_object=signal_text[:1024],
                    confidence=signal_conf,
                    verification_status="unverified",
                    source_provider="company_website",
                    source_url=website_url,
                    quoted_text=signal_text[:2048],
                    raw_payload={
                        "signal": signal_text,
                        "source": "website",
                        "website": website_url,
                    },
                )
            )

            for person_name in _extract_person_names_from_signal(
                signal_text,
                limit=3,
                seed_name=seed_name,
                source_url=website_url,
            ):
                claims.append(
                    ExtendedScreenClaim(
                        run_id=run.id,
                        invoice_id=run.invoice_id,
                        entity_id=run.entity_id,
                        claim_type="website_associated_person",
                        claim_subject=seed_name[:512],
                        claim_object=person_name[:1024],
                        confidence=0.74,
                        verification_status="unverified",
                        source_provider="company_website",
                        source_url=website_url,
                        quoted_text=signal_text[:2048],
                        raw_payload={
                            "signal": signal_text,
                            "extracted_name": person_name,
                            "source": "website",
                            "website": website_url,
                        },
                    )
                )

            for company_name in _extract_company_names_from_signal(
                signal_text,
                limit=2,
                seed_name=seed_name,
                source_url=website_url,
            ):
                claims.append(
                    ExtendedScreenClaim(
                        run_id=run.id,
                        invoice_id=run.invoice_id,
                        entity_id=run.entity_id,
                        claim_type="website_associated_company",
                        claim_subject=seed_name[:512],
                        claim_object=company_name[:1024],
                        confidence=0.72,
                        verification_status="unverified",
                        source_provider="company_website",
                        source_url=website_url,
                        quoted_text=signal_text[:2048],
                        raw_payload={
                            "signal": signal_text,
                            "extracted_company": company_name,
                            "source": "website",
                            "website": website_url,
                        },
                    )
                )

    ownership = payload.get("ownership_management") or {}
    if isinstance(ownership, dict):
        def _append_ownership_claims(rows: Any, claim_type: str) -> None:
            if not isinstance(rows, list):
                return
            for row in rows:
                if not isinstance(row, dict):
                    continue
                name = str(row.get("name") or "").strip()
                if len(name) < 3:
                    continue
                claims.append(
                    ExtendedScreenClaim(
                        run_id=run.id,
                        invoice_id=run.invoice_id,
                        entity_id=run.entity_id,
                        claim_type=claim_type,
                        claim_subject=seed_name[:512],
                        claim_object=name[:1024],
                        confidence=_confidence_value(row.get("confidence")),
                        verification_status=str(row.get("verification_status") or "unverified"),
                        source_provider=str(row.get("source_provider") or "ownership_profile")[:32],
                        source_url=str(row.get("source_url") or "").strip() or None,
                        quoted_text=str(row.get("evidence_excerpt") or "").strip()[:2048] or None,
                        raw_payload=row,
                    )
                )

        parent = ownership.get("ultimate_parent")
        if isinstance(parent, dict):
            _append_ownership_claims([parent], "ultimate_parent")
        _append_ownership_claims(ownership.get("direct_owners"), "direct_owner")
        _append_ownership_claims(ownership.get("beneficial_owners"), "beneficial_owner")
        _append_ownership_claims(ownership.get("board_members"), "board_member")
        _append_ownership_claims(ownership.get("executives"), "executive")

    for hit in payload.get("sanctions_hits") or []:
        if not isinstance(hit, dict):
            continue
        target_name = str(hit.get("target_name") or "").strip()
        matched_name = str(hit.get("matched_name") or "").strip()
        dataset = str(hit.get("dataset") or "").strip()
        dataset_entity_id = str(hit.get("dataset_entity_id") or "").strip()
        if not target_name or not dataset:
            continue
        source_provider = (
            str(hit.get("source_provider") or "sanctions_match").strip()
            or "sanctions_match"
        )
        source_url = None
        if dataset == "UK_SANCTIONS":
            source_url = _UK_SANCTIONS_CSV_URL
        elif dataset == "WORLD_BANK_DEBARRED":
            source_url = _WORLD_BANK_DEBARRED_API_URL
        claims.append(
            ExtendedScreenClaim(
                run_id=run.id,
                invoice_id=run.invoice_id,
                entity_id=run.entity_id,
                claim_type="sanctions_watchlist_match",
                claim_subject=target_name[:512],
                claim_object=f"{dataset}:{dataset_entity_id or matched_name}"[:1024],
                confidence=_confidence_value(hit.get("score")),
                verification_status="verified",
                source_provider=source_provider[:32],
                source_url=source_url,
                quoted_text=f"{target_name} ~ {matched_name} ({dataset})"[:2048],
                raw_payload=hit,
            )
        )

    _resolve_claim_verification(
        claims,
        selected_candidate_qids=selected_candidate_qids,
        sanctions_hit_names=sanctions_hit_names,
    )
    return claims


async def _persist_phase1_artifacts(
    session: AsyncSession,
    *,
    run: ExtendedScreenRun,
    payload: dict[str, Any],
    seed_name: str,
) -> None:
    await session.execute(
        delete(ExtendedScreenSource).where(ExtendedScreenSource.run_id == run.id)
    )
    await session.execute(
        delete(ExtendedScreenClaim).where(ExtendedScreenClaim.run_id == run.id)
    )
    await session.flush()

    for row in _build_phase1_sources(run=run, payload=payload):
        session.add(row)
    for row in _build_phase1_claims(run=run, payload=payload, seed_name=seed_name):
        session.add(row)


async def _build_extended_payload(
    *,
    session: AsyncSession,
    seed_entity: Entity,
    invoice: Invoice,
    aggressiveness: int,
    run_config: dict[str, Any] | None,
) -> dict[str, Any]:
    profile = _profile_from_aggressiveness(aggressiveness)
    config = _normalize_run_config(run_config)
    seed_name = seed_entity.name.strip()
    configured_sources = ["wikidata", "gleif", "company_website"]
    if config["enable_brreg"]:
        configured_sources.append("brreg")
    if config["enable_uk_sanctions"]:
        configured_sources.append("uk_sanctions")
    if config["enable_world_bank_debarred"]:
        configured_sources.append("world_bank_debarred")
    if config["enable_ai_entity_research"]:
        configured_sources.append("ai_entity_research")
    if config["enable_ai_web_search"]:
        configured_sources.append("ai_web_search")

    payload: dict[str, Any] = {
        "meta": {
            "aggressiveness": aggressiveness,
            "max_hops": 1,
            "min_edge_confidence": profile.min_edge_confidence,
            "min_edge_confidence_effective": config["min_edge_confidence"],
            "min_candidate_confidence": profile.min_candidate_confidence,
            "max_candidates": profile.max_candidates,
            "max_search_queries": profile.max_search_queries,
            "max_search_results_per_query": profile.max_search_results_per_query,
            "max_search_pages_to_fetch": profile.max_search_pages_to_fetch,
            "source_mode": "free_sources_only",
            "selected_only": config["selected_only"],
            "sanctions_near_only": config["sanctions_near_only"],
            "enable_brreg": config["enable_brreg"],
            "enable_uk_sanctions": config["enable_uk_sanctions"],
            "enable_world_bank_debarred": config["enable_world_bank_debarred"],
            "enable_ai_entity_research": config["enable_ai_entity_research"],
            "enable_ai_web_search": config["enable_ai_web_search"],
        },
        "seed": {
            "entity_id": str(seed_entity.id),
            "name": seed_name,
            "entity_type": seed_entity.entity_type.value,
            "country": seed_entity.country,
            "invoice_id": str(invoice.id),
        },
        "sources": configured_sources,
        "gleif_matches": [],
        "wikidata_candidates": [],
        "associations": [],
        "relation_decisions": [],
        "sanctions_hits": [],
        "external_source_status": [],
        "brreg_findings": [],
        "country_exposure": [],
        "website_findings": [],
        "ownership_management": {
            "ultimate_parent": None,
            "direct_owners": [],
            "beneficial_owners": [],
            "board_members": [],
            "executives": [],
            "source_evidence": [],
            "external_profiles": [],
            "screening_hits": [],
            "risk_country_signals": [],
            "diagnostics": [],
        },
        "summary": {"notes": []},
    }

    headers = {
        "User-Agent": "xlent-compliance-mvp/0.1 (extended-screening)",
        "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
    }

    async with httpx.AsyncClient(
        timeout=_REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers=headers,
    ) as client:
        gleif_rows = await _gleif_search(client, seed_name, page_size=5)
        gleif_matches: list[dict[str, Any]] = []
        for row in gleif_rows:
            attrs = row.get("attributes") or {}
            entity = attrs.get("entity") or {}
            legal_name_obj = entity.get("legalName") or {}
            legal_name = str(legal_name_obj.get("name") or "").strip()
            if not legal_name:
                continue

            match_conf = _name_similarity(seed_name, legal_name)
            lei = str(attrs.get("lei") or "").strip()
            jurisdiction = str(entity.get("jurisdiction") or "").strip()
            legal_form_obj = entity.get("legalForm") or {}
            legal_form = (
                str(legal_form_obj.get("id") or "").strip()
                if isinstance(legal_form_obj, dict)
                else str(legal_form_obj or "").strip()
            )
            entity_status = str(entity.get("status") or "").strip()

            gleif_matches.append(
                {
                    "lei": lei,
                    "legal_name": legal_name,
                    "jurisdiction": jurisdiction or None,
                    "legal_form": legal_form or None,
                    "entity_status": entity_status or None,
                    "confidence": round(match_conf, 4),
                    "source_url": f"https://search.gleif.org/#/record/{lei}" if lei else None,
                    "raw": row,
                }
            )

        gleif_matches.sort(key=lambda item: float(item.get("confidence") or 0.0), reverse=True)
        payload["gleif_matches"] = gleif_matches[:5]

        search_hits = await _wikidata_search(
            client,
            seed_name,
            limit=max(8, profile.max_candidates * 3),
        )
        candidates = _build_candidates(seed_name, search_hits, profile)

        if not candidates and search_hits:
            # Fallback to top hit if scores are low, so user still sees traceability.
            top = search_hits[0]
            qid = str(top.get("id") or "").strip()
            label = str(top.get("label") or qid)
            if qid:
                candidates = [
                    _Candidate(
                        qid=qid,
                        label=label,
                        description=str(top.get("description") or "").strip() or None,
                        aliases=[
                            str(a).strip()
                            for a in (top.get("aliases") or [])
                            if str(a).strip()
                        ],
                        confidence=_name_similarity(seed_name, label),
                    )
                ]

        if not candidates:
            payload["summary"]["notes"].append("Ingen Wikidata-kandidater over terskel.")
        candidate_docs = (
            await _wikidata_get_entities(client, [c.qid for c in candidates])
            if candidates
            else {}
        )

        filtered_candidates: list[_Candidate] = []
        candidate_rows: list[dict[str, Any]] = []
        for candidate in candidates:
            doc = candidate_docs.get(candidate.qid, {})
            candidate_type = _item_type(doc)
            description = _description_of(doc) or candidate.description
            selected, reason = _candidate_allowed_for_seed(
                seed_entity=seed_entity,
                candidate=candidate,
                candidate_type=candidate_type,
                description=description,
            )
            candidate_rows.append(
                {
                    "qid": candidate.qid,
                    "label": candidate.label,
                    "description": description,
                    "confidence": candidate.confidence,
                    "candidate_type": candidate_type,
                    "selected": selected,
                    "reason": reason,
                }
            )
            if selected:
                filtered_candidates.append(candidate)

        payload["wikidata_candidates"] = candidate_rows

        if not filtered_candidates:
            payload["summary"]["notes"].append(
                "Kandidater funnet, men filtrert bort av presisjonsregler."
            )
            payload["summary"]["notes"].append(
                "Fortsetter med web-/kildesøk uten Wikidata-relasjonsgraf."
            )

        # Gather related IDs in one pass, then bulk-fetch details.
        related_ids: list[str] = []
        for candidate in filtered_candidates:
            doc = candidate_docs.get(candidate.qid)
            if not doc:
                continue
            for prop in _RELATION_PROPS:
                related_ids.extend(
                    _extract_claim_entity_ids(
                        doc,
                        prop,
                        limit=profile.max_relations_per_candidate,
                    )
                )

        related_ids = list(dict.fromkeys(related_ids))
        related_docs = await _wikidata_get_entities(client, related_ids) if related_ids else {}

        associations: list[dict[str, Any]] = []
        websites_to_scan: list[str] = []

        for candidate in filtered_candidates:
            doc = candidate_docs.get(candidate.qid)
            if not doc:
                continue

            candidate_type = _item_type(doc)
            payload["summary"]["notes"].append(
                "Wikidata-kandidat valgt: "
                f"{candidate.label} ({candidate.qid}), "
                f"confidence {candidate.confidence:.2f}."
            )

            websites = _extract_claim_strings(doc, "P856", limit=3)
            for raw_url in websites:
                normalized = _normalize_url(raw_url)
                if normalized:
                    websites_to_scan.append(normalized)

            for prop, relation in _RELATION_PROPS.items():
                targets = _extract_claim_entity_ids(
                    doc,
                    prop,
                    limit=profile.max_relations_per_candidate,
                )
                for target_qid in targets:
                    target_doc = related_docs.get(target_qid, {})
                    target_name = _label_of(target_doc) or target_qid
                    target_description = _description_of(target_doc)
                    target_type = _item_type(target_doc)
                    if target_type == "unknown":
                        target_type = _relation_target_type(relation)

                    edge_confidence = round(
                        max(candidate.confidence - 0.08, profile.min_edge_confidence),
                        4,
                    )

                    associations.append(
                        {
                            "source": "wikidata",
                            "source_qid": candidate.qid,
                            "source_label": candidate.label,
                            "source_type": candidate_type,
                            "relation": relation,
                            "edge_confidence": edge_confidence,
                            "target": {
                                "qid": target_qid,
                                "name": target_name,
                                "description": target_description,
                                "type": target_type,
                            },
                        }
                    )

        # Deduplicate associations.
        deduped_associations: list[dict[str, Any]] = []
        seen_assoc: set[tuple[str, str, str]] = set()
        for assoc in associations:
            key = (
                str(assoc.get("source_qid") or ""),
                str(assoc.get("relation") or ""),
                str((assoc.get("target") or {}).get("qid") or ""),
            )
            if key in seen_assoc:
                continue
            seen_assoc.add(key)
            deduped_associations.append(assoc)

        brreg_candidate_names = [seed_name]
        brreg_candidate_names.extend(
            str((assoc.get("target") or {}).get("name") or "").strip()
            for assoc in deduped_associations
            if str((assoc.get("target") or {}).get("type") or "") == "company"
        )
        brreg_candidate_names = [name for name in brreg_candidate_names if len(name) >= 4]
        if config["enable_brreg"]:
            brreg_findings, brreg_associations = await _search_brreg_companies(
                client,
                names=list(dict.fromkeys(brreg_candidate_names))[:8],
            )
            payload["brreg_findings"] = brreg_findings
            deduped_associations.extend(brreg_associations)

        selected_candidate_qids = {
            str(row.get("qid"))
            for row in payload["wikidata_candidates"]
            if bool(row.get("selected"))
        }
        relation_decisions: list[dict[str, Any]] = []
        effective_associations: list[dict[str, Any]] = []

        for assoc in deduped_associations:
            relation = str(assoc.get("relation") or "")
            source_qid = str(assoc.get("source_qid") or "")
            source_kind = str(assoc.get("source") or "wikidata")
            edge_confidence = float(assoc.get("edge_confidence") or 0.0)
            target = assoc.get("target") or {}
            target_qid = str(target.get("qid") or "")
            target_name = str(target.get("name") or "")
            target_type = str(target.get("type") or "unknown")

            include = True
            reasons: list[str] = []
            if (
                config["selected_only"]
                and source_kind == "wikidata"
                and source_qid
                and source_qid not in selected_candidate_qids
            ):
                include = False
                reasons.append("source_candidate_not_selected")

            if edge_confidence < float(config["min_edge_confidence"]):
                include = False
                reasons.append("below_min_edge_confidence")

            if config["sanctions_near_only"] and relation not in _SANCTIONS_NEAR_RELATIONS:
                include = False
                reasons.append("non_sanctions_near_relation")

            relation_decisions.append(
                {
                    "source": source_kind,
                    "source_qid": source_qid,
                    "target_qid": target_qid,
                    "target_name": target_name,
                    "target_type": target_type,
                    "relation": relation,
                    "edge_confidence": edge_confidence,
                    "included": include,
                    "excluded_reason": ",".join(reasons) if reasons else None,
                }
            )
            if include:
                effective_associations.append(assoc)

        payload["relation_decisions"] = relation_decisions
        payload["associations"] = effective_associations

        seed_hits = await _sanctions_check_seed_entity(
            seed_name=seed_name,
            seed_entity_type=seed_entity.entity_type.value,
            seed_country=seed_entity.country,
        )
        sanctions_hits = seed_hits + await _sanctions_check_associations(
            effective_associations,
            profile,
        )
        external_names = [
            {
                "name": seed_name,
                "relation": "seed_name",
                "source_qid": str(seed_entity.id),
                "target_type": seed_entity.entity_type.value,
            }
        ]
        external_names.extend(
            {
                "name": str((assoc.get("target") or {}).get("name") or "").strip(),
                "relation": str(assoc.get("relation") or "related_to"),
                "source_qid": str(assoc.get("source_qid") or ""),
                "target_type": str((assoc.get("target") or {}).get("type") or "unknown"),
            }
            for assoc in effective_associations
        )
        external_names = [row for row in external_names if len(str(row.get("name") or "")) >= 4]

        external_hits, external_sources = await _match_external_sanctions(
            session,
            names=external_names,
            enable_uk_sanctions=config["enable_uk_sanctions"],
            enable_world_bank_debarred=config["enable_world_bank_debarred"],
        )
        payload["external_source_status"] = [
            {
                "provider": SOURCE_BRREG_LOOKUP,
                "source_url": _BRREG_ENHETER_API_URL,
                "enabled": config["enable_brreg"],
                "status": "ok" if config["enable_brreg"] else "disabled",
                "error": None,
                "record_count": len(payload.get("brreg_findings") or []),
                "fetched_at": datetime.now(UTC).isoformat()
                if config["enable_brreg"]
                else None,
            },
            *external_sources,
        ]

        all_hits = sanctions_hits + external_hits
        deduped_hits: list[dict[str, Any]] = []
        seen_hit: set[tuple[str, str, str]] = set()
        for hit in all_hits:
            key = (
                str(hit.get("dataset") or ""),
                str(hit.get("target_name") or "").lower(),
                str(hit.get("matched_name") or "").lower(),
            )
            if key in seen_hit:
                continue
            seen_hit.add(key)
            try:
                raw_score = float(hit.get("score") or 0.0)
            except (TypeError, ValueError):
                raw_score = 0.0
            hit["weighted_score"] = _weighted_hit_score(hit, raw_score=raw_score)
            deduped_hits.append(hit)
        deduped_hits.sort(key=lambda item: float(item.get("weighted_score") or 0.0), reverse=True)
        payload["sanctions_hits"] = deduped_hits

        country_exposure = _risk_countries_from_associations(effective_associations)

        website_findings: list[dict[str, Any]] = []
        websites = list(dict.fromkeys(websites_to_scan))
        for website in websites[: profile.max_site_candidates]:
            finding = await _scan_company_website(client, website, profile)
            website_findings.append(finding)

        payload["website_findings"] = website_findings

        ownership_profile = await _build_ownership_management_profile(
            client,
            query_profile=profile,
            seed_name=seed_name,
            seed_country=seed_entity.country,
            selected_candidates=filtered_candidates,
            candidate_docs=candidate_docs,
            associations=effective_associations,
            website_findings=website_findings,
            brreg_findings=payload.get("brreg_findings") or [],
            enable_ai_entity_research=bool(config["enable_ai_entity_research"]),
            enable_ai_web_search=bool(config["enable_ai_web_search"]),
        )
        payload["ownership_management"] = ownership_profile

        ownership_hits = await _screen_ownership_profile_entities(
            session,
            ownership_profile=ownership_profile,
            enable_uk_sanctions=bool(config["enable_uk_sanctions"]),
            enable_world_bank_debarred=bool(config["enable_world_bank_debarred"]),
        )
        if ownership_hits:
            payload["sanctions_hits"].extend(ownership_hits)
            ownership_profile["screening_hits"] = ownership_hits
            reweighted_hits: list[dict[str, Any]] = []
            seen_ownership_hit: set[tuple[str, str, str]] = set()
            for hit in payload["sanctions_hits"]:
                key = (
                    str(hit.get("dataset") or ""),
                    str(hit.get("target_name") or "").lower(),
                    str(hit.get("matched_name") or "").lower(),
                )
                if key in seen_ownership_hit:
                    continue
                seen_ownership_hit.add(key)
                try:
                    raw_score = float(hit.get("score") or 0.0)
                except (TypeError, ValueError):
                    raw_score = 0.0
                hit["weighted_score"] = _weighted_hit_score(hit, raw_score=raw_score)
                reweighted_hits.append(hit)
            reweighted_hits.sort(
                key=lambda item: float(item.get("weighted_score") or 0.0),
                reverse=True,
            )
            payload["sanctions_hits"] = reweighted_hits

        for finding in website_findings:
            country_exposure.extend(_risk_countries_from_site(finding))
        country_exposure.extend(ownership_profile.get("risk_country_signals") or [])

        # Deduplicate country exposure.
        deduped_country_exposure: list[dict[str, Any]] = []
        seen_country: set[tuple[str, str, str]] = set()
        for exposure in country_exposure:
            key = (
                str(exposure.get("relation") or ""),
                str(exposure.get("country") or "").lower(),
                str(exposure.get("source") or ""),
            )
            if key in seen_country:
                continue
            seen_country.add(key)
            deduped_country_exposure.append(exposure)

        payload["country_exposure"] = deduped_country_exposure

        summary_risk, summary_text = _summary_from_payload(payload)
        payload["summary"] = {
            "risk": summary_risk,
            "text": summary_text,
            "notes": payload["summary"].get("notes", []),
            "counts": {
                "candidates": len(payload["wikidata_candidates"]),
                "candidates_selected": sum(
                    1
                    for row in payload["wikidata_candidates"]
                    if bool((row or {}).get("selected"))
                ),
                "associations_total": len(deduped_associations),
                "associations": len(payload["associations"]),
                "sanctions_hits": len(payload["sanctions_hits"]),
                "external_sources": len(payload["external_source_status"]),
                "brreg_findings": len(payload["brreg_findings"]),
                "country_exposure": len(payload["country_exposure"]),
                "website_findings": len(payload["website_findings"]),
                "ownership_evidence": len(
                    (payload.get("ownership_management") or {}).get("source_evidence") or []
                ),
                "web_queries_planned": int(
                    (
                        (payload.get("ownership_management") or {})
                        .get("web_research", {})
                        .get("queries_planned")
                    )
                    or 0
                ),
                "web_queries_executed": int(
                    (
                        (payload.get("ownership_management") or {})
                        .get("web_research", {})
                        .get("queries_executed")
                    )
                    or 0
                ),
                "web_results_found": int(
                    (
                        (payload.get("ownership_management") or {})
                        .get("web_research", {})
                        .get("results_found")
                    )
                    or 0
                ),
                "web_pages_fetched": int(
                    (
                        (payload.get("ownership_management") or {})
                        .get("web_research", {})
                        .get("pages_fetched")
                    )
                    or 0
                ),
                "web_pages_with_signal": int(
                    (
                        (payload.get("ownership_management") or {})
                        .get("web_research", {})
                        .get("pages_with_signal")
                    )
                    or 0
                ),
                "web_fetch_errors": int(
                    (
                        (payload.get("ownership_management") or {})
                        .get("web_research", {})
                        .get("fetch_errors")
                    )
                    or 0
                ),
                "ownership_people_companies": sum(
                    len((payload.get("ownership_management") or {}).get(key) or [])
                    for key in (
                        "direct_owners",
                        "beneficial_owners",
                        "board_members",
                        "executives",
                    )
                ) + (
                    1
                    if isinstance(
                        (payload.get("ownership_management") or {}).get("ultimate_parent"),
                        dict,
                    )
                    else 0
                ),
                "relations_excluded": sum(
                    1
                    for row in payload["relation_decisions"]
                    if not bool((row or {}).get("included"))
                ),
            },
        }

        return payload


async def create_extended_screen_run(
    session: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    aggressiveness: int,
    run_config: dict[str, Any] | None = None,
) -> ExtendedScreenRun:
    """Opprett ny utvidet-screening-run (siste run vinner)."""
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} finnes ikke")

    entity = await session.get(Entity, entity_id)
    if not entity or entity.invoice_id != invoice_id:
        raise ValueError(f"Entity {entity_id} finnes ikke pa invoice {invoice_id}")

    # Siste run vinner: marker eldre aktive runs som failed/superseded.
    result = await session.execute(
        select(ExtendedScreenRun).where(
            ExtendedScreenRun.invoice_id == invoice_id,
            ExtendedScreenRun.entity_id == entity_id,
            ExtendedScreenRun.status.in_(["queued", "running"]),
        )
    )
    active_runs = result.scalars().all()
    for row in active_runs:
        row.status = "failed"
        row.error_message = "Superseded by newer run"
        row.finished_at = datetime.now(UTC)

    run = ExtendedScreenRun(
        invoice_id=invoice_id,
        entity_id=entity_id,
        aggressiveness=max(0, min(100, int(aggressiveness))),
        run_config=_normalize_run_config(run_config),
        status="queued",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    return run


async def get_extended_screen_run(
    session: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
) -> ExtendedScreenRun:
    """Hent en run og verifiser at den tilhoerer riktig invoice + entity."""
    run = await session.get(ExtendedScreenRun, run_id)
    if not run:
        raise ValueError(f"Run {run_id} finnes ikke")

    if run.invoice_id != invoice_id or run.entity_id != entity_id:
        raise ValueError("Run matcher ikke invoice/entity")

    return run


async def execute_extended_screen_run(run_id: uuid.UUID) -> None:
    """Kjor utvidet screening for en eksisterende run-id."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        run = await session.get(ExtendedScreenRun, run_id)
        if not run:
            logger.warning("extended_screen_run_missing", run_id=str(run_id))
            return

        if run.status not in {"queued", "running"}:
            logger.info(
                "extended_screen_run_skip_status",
                run_id=str(run_id),
                status=run.status,
            )
            return

        run.status = "running"
        run.started_at = datetime.now(UTC)
        run.error_message = None
        await session.commit()

        try:
            entity = await session.get(Entity, run.entity_id)
            invoice = await session.get(Invoice, run.invoice_id)
            if not entity or not invoice:
                raise ValueError("Mangler seed-entity eller invoice")

            timeout_seconds = int(
                getattr(get_settings(), "extended_screen_run_timeout_seconds", 240) or 240
            )
            payload = await asyncio.wait_for(
                _build_extended_payload(
                    session=session,
                    seed_entity=entity,
                    invoice=invoice,
                    aggressiveness=run.aggressiveness,
                    run_config=run.run_config,
                ),
                timeout=max(60, timeout_seconds),
            )
            await _persist_phase1_artifacts(
                session,
                run=run,
                payload=payload,
                seed_name=entity.name,
            )

            summary = payload.get("summary") or {}
            run.summary_risk = str(summary.get("risk") or "low")[:16]
            run.summary_text = str(summary.get("text") or "")[:1024] or None
            run.result_payload = payload
            run.status = "completed"
            run.finished_at = datetime.now(UTC)
            await session.commit()

            logger.info(
                "extended_screen_run_completed",
                run_id=str(run.id),
                invoice_id=str(run.invoice_id),
                entity_id=str(run.entity_id),
                risk=run.summary_risk,
            )
        except asyncio.TimeoutError:
            logger.exception(
                "extended_screen_run_timeout",
                run_id=str(run.id),
            )
            run.status = "failed"
            run.error_message = (
                "Utvidet screening timet ut før ferdigstilling. "
                "Prøv lavere aggressivitet eller smalere scope."
            )[:1000]
            run.finished_at = datetime.now(UTC)
            await session.commit()
        except Exception as exc:
            logger.exception(
                "extended_screen_run_failed",
                run_id=str(run.id),
                error=str(exc),
            )
            run.status = "failed"
            run.error_message = str(exc)[:1000]
            run.finished_at = datetime.now(UTC)
            await session.commit()


async def add_extended_screen_feedback(
    session: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
    feedback_label: str,
    target_qid: str | None,
    target_name: str | None,
    note: str | None,
) -> ExtendedScreenFeedback:
    run = await session.get(ExtendedScreenRun, run_id)
    if not run:
        raise ValueError(f"Run {run_id} finnes ikke")
    if run.invoice_id != invoice_id or run.entity_id != entity_id:
        raise ValueError("Run matcher ikke invoice/entity")

    feedback = ExtendedScreenFeedback(
        run_id=run_id,
        invoice_id=invoice_id,
        entity_id=entity_id,
        feedback_label=feedback_label,
        target_qid=(target_qid.strip() if target_qid else None),
        target_name=(target_name.strip() if target_name else None),
        note=(note.strip() if note else None),
    )
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback


async def list_extended_screen_feedback(
    session: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
) -> list[ExtendedScreenFeedback]:
    run = await session.get(ExtendedScreenRun, run_id)
    if not run:
        raise ValueError(f"Run {run_id} finnes ikke")
    if run.invoice_id != invoice_id or run.entity_id != entity_id:
        raise ValueError("Run matcher ikke invoice/entity")

    result = await session.execute(
        select(ExtendedScreenFeedback).where(
            ExtendedScreenFeedback.run_id == run_id
        ).order_by(ExtendedScreenFeedback.created_at.desc())
    )
    return list(result.scalars().all())


async def list_extended_screen_sources(
    session: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
) -> list[ExtendedScreenSource]:
    run = await session.get(ExtendedScreenRun, run_id)
    if not run:
        raise ValueError(f"Run {run_id} finnes ikke")
    if run.invoice_id != invoice_id or run.entity_id != entity_id:
        raise ValueError("Run matcher ikke invoice/entity")

    result = await session.execute(
        select(ExtendedScreenSource)
        .where(ExtendedScreenSource.run_id == run_id)
        .order_by(ExtendedScreenSource.fetched_at.desc())
    )
    return list(result.scalars().all())


async def list_extended_screen_claims(
    session: AsyncSession,
    *,
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
) -> list[ExtendedScreenClaim]:
    run = await session.get(ExtendedScreenRun, run_id)
    if not run:
        raise ValueError(f"Run {run_id} finnes ikke")
    if run.invoice_id != invoice_id or run.entity_id != entity_id:
        raise ValueError("Run matcher ikke invoice/entity")

    result = await session.execute(
        select(ExtendedScreenClaim)
        .where(ExtendedScreenClaim.run_id == run_id)
        .order_by(ExtendedScreenClaim.created_at.desc())
    )
    return list(result.scalars().all())
