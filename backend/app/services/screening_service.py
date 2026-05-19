"""
Sanksjonsscreening-tjeneste (Sprint 3).

Flyt for screen_invoice():

  FASE 1 — Land-embargo-sjekk (regel-basert, ingen nettverkskall)
    1a. Sjekk invoice.destination_country mot embargo-lista
    1b. Sjekk alle relevante entiteters .country mot embargo-lista
    Treff pa comprehensive embargo → umiddelbart RED + ScreeningResult
    Treff pa sectoral embargo → bidrar til YELLOW med forklaring

  FASE 2 — Entity-name matching via yente (fuzzy matching)
    2a. Hent alle entiteter med screenbared rolle
    2b. Batch-match mot yente (parallelt, semaphore-begrenset)
    2c. Opprett ScreeningResult per treff

  FASE 3 — Beregn compliance_score og sett status
    Verste-vinner: confirmed_match → RED, potential_match → YELLOW, ellers GREEN

Feilhåndtering:
  Land-sjekken (fase 1) feiler aldri — den er rent lokalt.
  Yente-feil (fase 2): dersom yente ikke svarer for NOEN entitet,
    settes compliance_score = None og status = SCREENING_FAILED.
    Operatoren ser "Screening feilet" i UI og kan prove igjen.
  Dersom yente feiler for NOEN (men ikke alle) → fortsett med delresultat,
    logg advarsel.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.data.logistics_domains import LOGISTICS_DOMAINS, is_logistics_domain
from app.models.entity import Entity, EntityRole
from app.models.invoice import ComplianceScore, Invoice, InvoiceDirection, InvoiceStatus
from app.models.screening import MatchStatus, ScreeningResult
from app.models.screening_run import ScreeningCandidate, ScreeningRun
from app.sanctions.embargo import EmbargoEntry, check_country
from app.sanctions.yente_client import YenteMatch, get_yente_client
from app.services.pipeline_event_service import append_pipeline_event
from app.services import audit_service
from app.services import rule_engine_service

logger = get_logger(__name__)


class ScreeningLockUnavailableError(RuntimeError):
    """Kastes når en annen transaksjon allerede screener samme invoice."""


# Roller vi screener: alle identifiserte parter i fakturaen.
_SCREENED_ROLES = set(EntityRole)

# Dataset-navn brukt i ScreeningResult nar treffet kommer fra landsjekk
_EMBARGO_DATASET = "country_embargo"
_EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)
_GENERIC_EMAIL_PARTS = {
    "admin",
    "accounts",
    "accounting",
    "ap",
    "ar",
    "billing",
    "compliance",
    "contact",
    "finance",
    "hello",
    "help",
    "info",
    "invoice",
    "invoices",
    "mail",
    "noreply",
    "no-reply",
    "office",
    "orders",
    "payment",
    "payments",
    "procurement",
    "sales",
    "service",
    "support",
    "team",
}
_PUBLIC_EMAIL_DOMAINS = {
    "gmail.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
    "aol.com",
    "msn.com",
    "live.com",
}
_GENERIC_CANDIDATE_SINGLE_TOKENS = {
    "accounting",
    "accounts",
    "admin",
    "billing",
    "compliance",
    "contact",
    "customer",
    "department",
    "dispatch",
    "export",
    "finance",
    "import",
    "imports",
    "invoice",
    "invoices",
    "logistics",
    "office",
    "order",
    "orders",
    "payment",
    "payments",
    "procurement",
    "purchasing",
    "sales",
    "service",
    "shipping",
    "support",
    "team",
}
_GENERIC_CANDIDATE_PHRASES = {
    "accounts payable",
    "accounts receivable",
    "customer service",
    "export department",
    "import department",
    "logistics department",
    "purchasing department",
    "shipping department",
}
_NOISY_CANDIDATE_TOKENS = {
    "about",
    "careers",
    "consultation",
    "database",
    "events",
    "faq",
    "features",
    "heritage",
    "insights",
    "job",
    "jobs",
    "list",
    "menu",
    "navigation",
    "news",
    "organization",
    "portal",
    "resource",
    "resources",
    "result",
    "results",
    "search",
    "support",
    "tracker",
}
_NOISY_FRAGMENT_SPLIT_RE = re.compile(r"\s*[|•]\s*|\s+-\s+|\s+/\s+")
_NOISY_RAW_RE = re.compile(r"(?:\.theme--|v-application\{|text--primary|!important)")
_COMPANY_SUFFIXES = {
    "as",
    "ab",
    "ag",
    "bv",
    "co",
    "corp",
    "gmbh",
    "inc",
    "llc",
    "ltd",
    "nv",
    "oy",
    "oyj",
    "plc",
    "pte",
    "sa",
    "sarl",
    "sas",
}
_LABELED_PARTY_RE = re.compile(
    r"(?im)^(?:[-*]\s*)?"
    r"(buyer|seller|consignee|consignor|exporter|importer|notify(?: party)?|"
    r"end[\s-]?user|declared end[\s-]?user|technical contact|attention)\s*"
    r"[:\-]\s*(.+?)\s*$"
)
_HEADING_RE = re.compile(r"^\s*#{2,}\s+(.+?)\s*$")
_RAW_TEXT_SKIPPED_HEADINGS = {
    "commercial invoice",
    "shipment compliance notes",
    "shipment notes",
    "payment information",
    "exporter seller",
    "buyer consignee",
}
_PLAUSIBILITY_TRANSIT_COUNTRIES = {"AE", "KZ", "AM", "GE", "AZ", "UZ", "TM", "TJ", "KG"}
_PLAUSIBILITY_FOOD_KEYWORDS = {
    "seafood",
    "fish",
    "fisheries",
    "food",
    "beverage",
    "meat",
    "dairy",
    "agri",
    "agriculture",
    "farm",
}
_PLAUSIBILITY_INDUSTRIAL_KEYWORDS = {
    "hydraulic",
    "actuator",
    "impeller",
    "bearing",
    "gear",
    "gearbox",
    "pump",
    "valve",
    "servo",
    "plc",
    "sensor",
    "coupling",
    "machined",
}
_PLAUSIBILITY_FREE_ZONE_KEYWORDS = {
    "free zone",
    "fze",
    "ftz",
    "special economic zone",
    "saif zone",
    "jafza",
}
_PLAUSIBILITY_INTERMEDIARY_NAME_KEYWORDS = {
    "trading",
    "trader",
    "stores",
    "fze",
    "fzco",
    "general trading",
    "import export",
}
_DUPLICATE_ROLE_GROUP = {EntityRole.BUYER, EntityRole.CONSIGNEE, EntityRole.END_USER}


@dataclass
class _ScreeningCandidate:
    """Et konkret navnekall som skal matches mot sanksjonslistene."""

    key: str
    entity_id: uuid.UUID
    name: str
    entity_type: str
    country: str | None
    source: str
    primary: bool = False
    source_email: str | None = None


def _tokenize_candidate(value: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", value.lower()) if t]


def _is_generic_candidate(value: str) -> bool:
    tokens = _tokenize_candidate(value)
    if not tokens:
        return True
    joined = " ".join(tokens)
    if joined in _GENERIC_CANDIDATE_PHRASES:
        return True
    if len(tokens) == 1 and tokens[0] in _GENERIC_CANDIDATE_SINGLE_TOKENS:
        return True
    if all(token in _COMPANY_SUFFIXES for token in tokens):
        return True
    return False


def _candidate_quality_score(value: str) -> float:
    tokens = _tokenize_candidate(value)
    if not tokens:
        return -100.0
    non_generic = sum(
        1
        for token in tokens
        if token not in _GENERIC_CANDIDATE_SINGLE_TOKENS and len(token) >= 3
    )
    noisy = sum(1 for token in tokens if token in _NOISY_CANDIDATE_TOKENS)
    long_tokens = sum(1 for token in tokens if len(token) >= 5)
    return float(non_generic) + (0.2 * float(long_tokens)) - (1.4 * float(noisy))


def _choose_candidate_fragment(value: str) -> str:
    fragments = [
        part.strip()
        for part in _NOISY_FRAGMENT_SPLIT_RE.split(value)
        if part and part.strip()
    ]
    if not fragments:
        return value
    return max(fragments, key=_candidate_quality_score)


def _normalize_candidate_name(value: str) -> str | None:
    preclean = value.strip()
    if not preclean:
        return None
    if _NOISY_RAW_RE.search(preclean):
        return None

    fragment = _choose_candidate_fragment(preclean)
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", fragment).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if len(cleaned) < 4:
        return None
    tokens = _tokenize_candidate(cleaned)
    if not tokens:
        return None
    noisy = sum(1 for token in tokens if token in _NOISY_CANDIDATE_TOKENS)
    non_generic = sum(
        1
        for token in tokens
        if token not in _GENERIC_CANDIDATE_SINGLE_TOKENS and len(token) >= 3
    )
    if len(tokens) > 24:
        return None
    if noisy >= 3 and noisy / len(tokens) >= 0.35:
        return None
    if len(tokens) >= 6 and noisy >= 2 and non_generic <= 2:
        return None
    if _is_generic_candidate(cleaned):
        return None
    return cleaned


def _extract_emails(text: str | None) -> set[str]:
    if not text:
        return set()
    return {m.group(1).lower() for m in _EMAIL_RE.finditer(text)}


def _email_hints(email: str) -> list[str]:
    """Generer navnehints fra en e-postadresse for sanksjonsscreening.

    For e-poster med kjente logistikkdomener (fedex.com, dhl.com, maersk.com,
    osv.) hoppes domenedelen over — logistikkselskapets navn er ikke relevant
    som sanksjonskandidatnavn for parten bak fakturaen. Local-part-hints
    (f.eks. «john doe» fra «john.doe@dhl.com») screenes likevel som normalt.
    """
    if "@" not in email:
        return []
    local, domain = email.lower().split("@", 1)
    hints: set[str] = set()

    local_tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", local)
        if token and token not in _GENERIC_EMAIL_PARTS and not token.isdigit()
    ]
    if len(local_tokens) >= 2:
        hints.add(" ".join(local_tokens[:4]))
    elif local_tokens and len(local_tokens[0]) >= 8:
        hints.add(local_tokens[0])

    # Hopp over domenehint dersom domenet tilhører et kjent logistikkselskap.
    # Disse selskapene er legitime transportører og generer støy i screeningen.
    if domain not in _PUBLIC_EMAIL_DOMAINS and domain not in LOGISTICS_DOMAINS:
        root = domain.split(".", 1)[0]
        root_tokens = [
            token
            for token in re.split(r"[^a-z0-9]+", root)
            if token and token not in _GENERIC_EMAIL_PARTS and len(token) >= 3
        ]
        if len(root_tokens) >= 2:
            hints.add(" ".join(root_tokens[:4]))
        elif root_tokens and len(root_tokens[0]) >= 5:
            hints.add(root_tokens[0])

        compact_root = re.sub(r"[^a-z0-9]+", "", root)
        if len(compact_root) >= 7:
            hints.add(compact_root)

    normalized = []
    for hint in hints:
        normalized_hint = _normalize_candidate_name(hint)
        if normalized_hint:
            normalized.append(normalized_hint)
    return sorted(set(normalized))


def _extract_labeled_party_candidates(raw_text: str | None) -> list[tuple[str, str]]:
    """Trekk ut navnekandidater fra label-linjer og markdown-headings."""
    if not raw_text:
        return []

    candidates: list[tuple[str, str]] = []

    for match in _LABELED_PARTY_RE.finditer(raw_text):
        label = match.group(1).strip().lower()
        value = match.group(2).strip()
        if value:
            candidates.append((label, value))

    for line in raw_text.splitlines():
        heading_match = _HEADING_RE.match(line)
        if not heading_match:
            continue
        heading = heading_match.group(1).strip()
        heading_norm = " ".join(_tokenize_candidate(heading))
        if not heading_norm or heading_norm in _RAW_TEXT_SKIPPED_HEADINGS:
            continue
        candidates.append(("heading", heading))

    return candidates


def _pick_anchor_for_label(
    label: str,
    fallback_entity: Entity | None,
    by_role: dict[EntityRole, list[Entity]],
) -> Entity | None:
    label_norm = " ".join(_tokenize_candidate(label))
    preferred_roles: list[EntityRole] = []
    if any(k in label_norm for k in ("seller", "exporter")):
        preferred_roles = [EntityRole.SELLER, EntityRole.CONSIGNOR]
    elif any(k in label_norm for k in ("buyer", "consignee", "importer", "notify")):
        preferred_roles = [EntityRole.BUYER, EntityRole.CONSIGNEE, EntityRole.DELIVERY_ADDRESS]
    elif "end user" in label_norm:
        preferred_roles = [EntityRole.END_USER, EntityRole.BUYER]
    elif any(k in label_norm for k in ("technical contact", "attention")):
        preferred_roles = [EntityRole.SIGNATORY, EntityRole.BUYER, EntityRole.SELLER]
    elif "heading" in label_norm:
        preferred_roles = [EntityRole.BUYER, EntityRole.SELLER, EntityRole.CONSIGNEE]

    for role in preferred_roles:
        entities = by_role.get(role, [])
        if entities:
            return entities[0]
    return fallback_entity


def _candidate_key(entity_id: uuid.UUID, source: str, name: str, extra: str = "") -> str:
    payload = f"{entity_id}|{source}|{name}|{extra}".encode()
    digest = hashlib.sha256(payload).hexdigest()[:12]
    return f"{entity_id}:{digest}"


def _invoice_lock_key(invoice_id: uuid.UUID) -> int:
    """Deriver en stabil 64-bit noekkel for pg_advisory_xact_lock."""
    return int.from_bytes(invoice_id.bytes[:8], byteorder="big", signed=True)


def _build_screening_candidates(
    invoice: Invoice,
    entities_to_screen: list[Entity],
    all_entities: list[Entity],
) -> tuple[list[_ScreeningCandidate], dict[uuid.UUID, _ScreeningCandidate]]:
    """Bygg kandidatnavn fra entities + e-post i entities/raw_text."""
    candidates: list[_ScreeningCandidate] = []
    primary_by_entity: dict[uuid.UUID, _ScreeningCandidate] = {}
    seen: set[tuple[uuid.UUID, str, str]] = set()

    entity_map = {entity.id: entity for entity in entities_to_screen}
    by_role: dict[EntityRole, list[Entity]] = {}
    for entity in entities_to_screen:
        by_role.setdefault(entity.role, []).append(entity)
    fallback_entity = (
        entities_to_screen[0] if entities_to_screen else (all_entities[0] if all_entities else None)
    )
    domain_anchor: dict[str, uuid.UUID] = {}

    def _add_candidate(
        *,
        anchor: Entity,
        source: str,
        raw_value: str,
        extra: str = "",
        source_email: str | None = None,
        primary: bool = False,
    ) -> None:
        normalized_name = _normalize_candidate_name(raw_value)
        if not normalized_name:
            return
        key = (anchor.id, source, normalized_name)
        if key in seen:
            return
        seen.add(key)
        candidate = _ScreeningCandidate(
            key=_candidate_key(anchor.id, source, normalized_name, extra),
            entity_id=anchor.id,
            name=normalized_name,
            entity_type=anchor.entity_type.value if anchor.entity_type else "company",
            country=anchor.country,
            source=source,
            primary=primary,
            source_email=source_email,
        )
        candidates.append(candidate)
        if primary:
            primary_by_entity[anchor.id] = candidate

    for entity in entities_to_screen:
        _add_candidate(
            anchor=entity,
            source="entity_name",
            raw_value=entity.name,
            primary=True,
        )

        if entity.email and "@" in entity.email:
            email = entity.email.lower()
            domain = email.split("@", 1)[1]
            domain_anchor[domain] = entity.id
            if is_logistics_domain(domain):
                # Logistikkdomene — generer ikke domenehint (se _email_hints),
                # men logg for sporbarhet slik at UI kan vise informasjonen.
                logger.debug(
                    "logistics_domain_skipped",
                    entity_id=str(entity.id),
                    entity_name=entity.name,
                    domain=domain,
                )
            for hint in _email_hints(email):
                _add_candidate(
                    anchor=entity,
                    source="entity_email",
                    raw_value=hint,
                    extra=email,
                    source_email=email,
                )

    for email in _extract_emails(invoice.raw_text):
        if fallback_entity is None:
            break
        domain = email.split("@", 1)[1]
        anchor_id = domain_anchor.get(domain, fallback_entity.id)
        anchor = entity_map.get(anchor_id, fallback_entity)
        for hint in _email_hints(email):
            _add_candidate(
                anchor=anchor,
                source="raw_text_email",
                raw_value=hint,
                extra=email,
                source_email=email,
            )

    # Fallback: hent kandidater direkte fra label-linjer/headings i dokumentteksten.
    # Dette gir bedre recall når LLM-entitetsekstraksjon bommer pa partnavn.
    for label, value in _extract_labeled_party_candidates(invoice.raw_text):
        anchor = _pick_anchor_for_label(label, fallback_entity, by_role)
        if anchor is None:
            continue
        _add_candidate(
            anchor=anchor,
            source="raw_text_label",
            raw_value=value,
            extra=label,
        )

    # Sikrer at hver screenet entitet fortsatt far minst en primarkandidat.
    # Hvis navnet ble filtrert som generisk stoy, bruk originalnavn uten stoyfilter.
    for entity in entities_to_screen:
        if entity.id in primary_by_entity:
            continue
        cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", entity.name).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) < 4:
            continue
        key = (entity.id, "entity_name_fallback", cleaned)
        if key in seen:
            continue
        seen.add(key)
        fallback_candidate = _ScreeningCandidate(
            key=_candidate_key(entity.id, "entity_name_fallback", cleaned),
            entity_id=entity.id,
            name=cleaned,
            entity_type=entity.entity_type.value if entity.entity_type else "company",
            country=entity.country,
            source="entity_name_fallback",
            primary=True,
        )
        candidates.append(fallback_candidate)
        primary_by_entity[entity.id] = fallback_candidate

    return candidates, primary_by_entity


def _limit_candidates(
    candidates: list[_ScreeningCandidate],
    max_candidates: int,
) -> list[_ScreeningCandidate]:
    """Begrens kandidatvolum for å holde screening-responstid stabil."""
    limit = max(1, max_candidates)
    if len(candidates) <= limit:
        return candidates

    source_priority = {
        "entity_name": 0,
        "entity_name_fallback": 0,
        "entity_email": 1,
        "raw_text_email": 2,
        "raw_text_label": 3,
    }

    primary = [c for c in candidates if c.primary]
    non_primary = [c for c in candidates if not c.primary]
    non_primary.sort(
        key=lambda c: (
            source_priority.get(c.source, 9),
            len(c.name),
            c.name.lower(),
        )
    )

    if len(primary) >= limit:
        trimmed = primary[:limit]
    else:
        trimmed = primary + non_primary[: max(0, limit - len(primary))]

    logger.warning(
        "screening_candidates_trimmed",
        original_count=len(candidates),
        kept_count=len(trimmed),
        max_candidates=limit,
    )
    return trimmed


def _classify_match(score: float, confirmed: float, potential: float) -> MatchStatus:
    """Bestem MatchStatus basert pa score og konfigurasjonsterskler."""
    if score >= confirmed:
        return MatchStatus.CONFIRMED_MATCH
    if score >= potential:
        return MatchStatus.POTENTIAL_MATCH
    return MatchStatus.CLEAR


def _worst_compliance(statuses: list[MatchStatus]) -> ComplianceScore:
    """Beregn invoice ComplianceScore fra listen av enkelt-resultater."""
    if MatchStatus.CONFIRMED_MATCH in statuses:
        return ComplianceScore.RED
    if MatchStatus.POTENTIAL_MATCH in statuses:
        return ComplianceScore.YELLOW
    return ComplianceScore.GREEN


def _make_embargo_result(
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    entry: EmbargoEntry,
    status: MatchStatus,
) -> ScreeningResult:
    """Opprett ett ScreeningResult for et land-embargo-treff."""
    return ScreeningResult(
        id=uuid.uuid4(),
        invoice_id=invoice_id,
        entity_id=entity_id,
        dataset=_EMBARGO_DATASET,
        dataset_entity_id=entry.iso2,
        matched_name=entry.name,
        # Score 1.0 for comprehensive embargo, 0.80 for sectoral
        score=Decimal("1.0000") if entry.scope == "comprehensive" else Decimal("0.8000"),
        listed_on=None,
        status=status,
        raw_response={
            "sources": list(entry.sources),
            "scope": entry.scope,
            "note": entry.note,
            "check_type": "country_embargo",
        },
    )


def _collect_trade_plausibility_results(
    *,
    invoice: Invoice,
    entities_to_screen: list[Entity],
) -> list[ScreeningResult]:
    """Heuristisk plausibilitetskontroll (ikke direkte sanksjonstreff).

    Legger inn POTENTIAL_MATCH ved tydelige avvik:
      1) Bransje-vare mismatch (f.eks. seafood + hydrauliske industrideler)
      2) Frihandelssone-transitt i kjent omgaelsesland med tredjeland-destinasjon
    """
    raw_text = (invoice.raw_text or "").lower()
    destination = (invoice.destination_country or "").strip().upper()
    if not raw_text:
        return []

    buyers = [
        entity
        for entity in entities_to_screen
        if entity.role in {EntityRole.BUYER, EntityRole.CONSIGNEE, EntityRole.END_USER}
    ]
    if not buyers:
        return []

    records: list[ScreeningResult] = []
    seen_checks: set[tuple[uuid.UUID, str]] = set()

    for buyer in buyers:
        buyer_name = (buyer.name or "").lower()
        buyer_addr = (buyer.address or "").lower()
        buyer_country = (buyer.country or "").strip().upper()
        cross_border = bool(destination and buyer_country and buyer_country != destination)

        food_hits = sorted(
            keyword for keyword in _PLAUSIBILITY_FOOD_KEYWORDS if keyword in buyer_name
        )
        industrial_hits = sorted(
            keyword for keyword in _PLAUSIBILITY_INDUSTRIAL_KEYWORDS if keyword in raw_text
        )

        if food_hits and cross_border and len(industrial_hits) >= 2:
            dedupe_key = (buyer.id, "industry_mismatch")
            if dedupe_key not in seen_checks:
                seen_checks.add(dedupe_key)
                records.append(
                    ScreeningResult(
                        id=uuid.uuid4(),
                        invoice_id=invoice.id,
                        entity_id=buyer.id,
                        dataset="trade_plausibility",
                        dataset_entity_id="industry_mismatch",
                        matched_name=buyer.name,
                        score=Decimal("0.7800"),
                        listed_on=None,
                        status=MatchStatus.POTENTIAL_MATCH,
                        raw_response={
                            "check_type": "trade_plausibility_industry_mismatch",
                            "buyer_country": buyer_country or None,
                            "destination_country": destination or None,
                            "food_name_hits": food_hits[:5],
                            "industrial_text_hits": industrial_hits[:6],
                        },
                    )
                )

        free_zone_hits = sorted(
            keyword
            for keyword in _PLAUSIBILITY_FREE_ZONE_KEYWORDS
            if keyword in buyer_name or keyword in buyer_addr
        )
        intermediary_hits = sorted(
            keyword
            for keyword in _PLAUSIBILITY_INTERMEDIARY_NAME_KEYWORDS
            if keyword in buyer_name
        )
        transit_route = buyer_country in _PLAUSIBILITY_TRANSIT_COUNTRIES
        if transit_route and cross_border and free_zone_hits and industrial_hits and intermediary_hits:
            dedupe_key = (buyer.id, "free_zone_transit")
            if dedupe_key not in seen_checks:
                seen_checks.add(dedupe_key)
                records.append(
                    ScreeningResult(
                        id=uuid.uuid4(),
                        invoice_id=invoice.id,
                        entity_id=buyer.id,
                        dataset="trade_plausibility",
                        dataset_entity_id="free_zone_transit",
                        matched_name=buyer.name,
                        score=Decimal("0.7600"),
                        listed_on=None,
                        status=MatchStatus.POTENTIAL_MATCH,
                        raw_response={
                            "check_type": "trade_plausibility_free_zone_transit",
                            "buyer_country": buyer_country or None,
                            "destination_country": destination or None,
                            "free_zone_hits": free_zone_hits[:5],
                            "intermediary_name_hits": intermediary_hits[:4],
                            "industrial_text_hits": industrial_hits[:6],
                        },
                    )
                )

    return records


def _normalize_duplicate_name(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


def _similarity_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return float(difflib.SequenceMatcher(None, left, right).ratio())


def _compact_text_for_duplicate(raw_text: str | None, max_chars: int = 1800) -> str:
    if not raw_text:
        return ""
    normalized = re.sub(r"\s+", " ", raw_text.lower()).strip()
    return normalized[:max_chars]


async def _collect_duplicate_invoice_results(
    *,
    session: AsyncSession,
    invoice: Invoice,
    entities_to_screen: list[Entity],
) -> list[ScreeningResult]:
    """Heuristisk duplikatkontroll for incoming invoices.

    Konservativ MVP:
      - Samme valuta og omtrent samme beløp
      - Lignende buyer/consignee-navn
      - Lignende tekst/fakturanummer
      - Unntar typiske manedlige gjentakelser
    """
    if invoice.direction != InvoiceDirection.INCOMING:
        return []
    if invoice.total_amount is None or not invoice.currency:
        return []

    current_buyer_names = [
        _normalize_duplicate_name(entity.name)
        for entity in entities_to_screen
        if entity.role in _DUPLICATE_ROLE_GROUP and entity.name
    ]
    current_buyer_names = [name for name in current_buyer_names if name]
    if not current_buyer_names:
        return []

    amount = Decimal(invoice.total_amount)
    if amount <= 0:
        return []

    lower = amount * Decimal("0.98")
    upper = amount * Decimal("1.02")
    cutoff = datetime.now(tz=UTC) - timedelta(days=365)

    candidate_stmt = (
        select(Invoice)
        .where(Invoice.id != invoice.id)
        .where(Invoice.direction == invoice.direction)
        .where(Invoice.currency == invoice.currency)
        .where(Invoice.total_amount.is_not(None))
        .where(Invoice.created_at >= cutoff)
        .where(Invoice.total_amount >= lower)
        .where(Invoice.total_amount <= upper)
        .order_by(Invoice.created_at.desc())
        .limit(120)
    )
    candidate_invoices = list((await session.execute(candidate_stmt)).scalars().all())
    if not candidate_invoices:
        return []

    candidate_ids = [inv.id for inv in candidate_invoices]
    entity_stmt = select(Entity).where(
        Entity.invoice_id.in_(candidate_ids),
        Entity.role.in_(list(_DUPLICATE_ROLE_GROUP)),
    )
    entity_rows = list((await session.execute(entity_stmt)).scalars().all())
    buyer_names_by_invoice: dict[uuid.UUID, list[str]] = {}
    for row in entity_rows:
        key = row.invoice_id
        buyer_names_by_invoice.setdefault(key, [])
        normalized = _normalize_duplicate_name(row.name)
        if normalized:
            buyer_names_by_invoice[key].append(normalized)

    current_number = _normalize_duplicate_name(invoice.invoice_number)
    current_text = _compact_text_for_duplicate(invoice.raw_text)
    current_date = invoice.invoice_date

    out: list[ScreeningResult] = []
    for candidate in candidate_invoices:
        previous_names = buyer_names_by_invoice.get(candidate.id, [])
        if not previous_names:
            continue

        name_similarity = max(
            (_similarity_ratio(now_name, prev_name) for now_name in current_buyer_names for prev_name in previous_names),
            default=0.0,
        )
        if name_similarity < 0.88:
            continue

        prev_amount = Decimal(candidate.total_amount or 0)
        if prev_amount <= 0:
            continue
        amount_ratio_diff = float(abs(amount - prev_amount) / max(amount, prev_amount))
        prev_number = _normalize_duplicate_name(candidate.invoice_number)
        number_similarity = _similarity_ratio(current_number, prev_number)
        text_similarity = _similarity_ratio(current_text, _compact_text_for_duplicate(candidate.raw_text))

        date_delta_days: int | None = None
        if current_date and candidate.invoice_date:
            date_delta_days = abs((current_date - candidate.invoice_date).days)

        # Unnta tydelig manedlig gjentakelse (abonnement/tjeneste)
        recurring_pattern = (
            date_delta_days is not None
            and 25 <= date_delta_days <= 40
            and amount_ratio_diff <= 0.01
            and number_similarity < 0.80
        )
        if recurring_pattern:
            continue

        suspicious = (
            (amount_ratio_diff <= 0.005 and name_similarity >= 0.92 and (date_delta_days is None or date_delta_days <= 14))
            or (number_similarity >= 0.90 and amount_ratio_diff <= 0.02 and name_similarity >= 0.88)
            or (text_similarity >= 0.97 and amount_ratio_diff <= 0.02 and (date_delta_days is None or date_delta_days <= 21))
        )
        if not suspicious:
            continue

        matched_name = candidate.invoice_number or candidate.original_filename or str(candidate.id)
        score = max(0.72, min(0.89, 0.72 + (name_similarity * 0.09) + (number_similarity * 0.05)))
        out.append(
            ScreeningResult(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                entity_id=entities_to_screen[0].id,
                dataset="duplicate_invoice",
                dataset_entity_id=str(candidate.id),
                matched_name=matched_name,
                score=Decimal(f"{score:.4f}"),
                listed_on=None,
                status=MatchStatus.POTENTIAL_MATCH,
                raw_response={
                    "check_type": "duplicate_invoice_similarity",
                    "matched_invoice_id": str(candidate.id),
                    "matched_invoice_number": candidate.invoice_number,
                    "matched_filename": candidate.original_filename,
                    "name_similarity": round(name_similarity, 4),
                    "number_similarity": round(number_similarity, 4),
                    "text_similarity": round(text_similarity, 4),
                    "amount_ratio_diff": round(amount_ratio_diff, 4),
                    "date_delta_days": date_delta_days,
                },
            )
        )
        break  # ett sterkt treff holder for MVP
    return out


async def screen_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
) -> Invoice:
    """Screen alle relevante entiteter for en invoice mot sanksjonslister.

    Returns:
        Den oppdaterte Invoice-instansen.

    Raises:
        ValueError: Invoice ikke funnet eller feil status.
    """
    settings = get_settings()
    confirmed_threshold = float(settings.screening_confirmed_threshold)
    match_threshold = float(settings.screening_match_threshold)

    # ── Hent og valider invoice ───────────────────────────────────────────────
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} finnes ikke")

    if invoice.status not in (
        InvoiceStatus.EXTRACTED,
        InvoiceStatus.SCREENED,
        InvoiceStatus.SCREENING,
        InvoiceStatus.SCREENING_FAILED,
    ):
        raise ValueError(
            f"Invoice {invoice_id} er i status {invoice.status!r} — "
            "forventet 'extracted', 'screening', 'screening_failed' eller 'screened'"
        )

    screening_run: ScreeningRun | None = None

    try:
        # Ikke-blokkerende advisory lock: dersom en annen jobb allerede screener
        # denne invoicen, avslutt denne kjøringen uten sideeffekter.
        lock_result = await session.execute(
            text("SELECT pg_try_advisory_xact_lock(:lock_key)"),
            {"lock_key": _invoice_lock_key(invoice_id)},
        )
        has_lock = bool(lock_result.scalar_one())
        if not has_lock:
            logger.info("screening_skip_already_running", invoice_id=str(invoice_id))
            await session.rollback()
            raise ScreeningLockUnavailableError(
                f"Invoice {invoice_id} is already being screened by another worker."
            )

        prev_status = invoice.status.value
        invoice.status = InvoiceStatus.SCREENING
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="screening",
            action="started",
            status_from=prev_status,
            status_to=InvoiceStatus.SCREENING.value,
        )
        await session.flush()
        logger.info("screening_started", invoice_id=str(invoice_id))

        # Slett eventuelle gamle screeningresultater (re-screening)
        await session.execute(
            delete(ScreeningResult).where(ScreeningResult.invoice_id == invoice_id)
        )
        await session.flush()

        # Hent alle entiteter
        result = await session.execute(
            select(Entity).where(Entity.invoice_id == invoice_id)
        )
        all_entities = result.scalars().all()
        entities_to_screen = [e for e in all_entities if e.role in _SCREENED_ROLES]

        logger.info(
            "screening_entities",
            invoice_id=str(invoice_id),
            total=len(all_entities),
            screening=len(entities_to_screen),
        )

        screening_run = ScreeningRun(
            invoice_id=invoice_id,
            status="running",
            candidate_count=0,
        )
        session.add(screening_run)
        await session.flush()

        all_statuses: list[MatchStatus] = []
        screening_records: list[ScreeningResult] = []

        # ══════════════════════════════════════════════════════════════════════
        # FASE 1 — Land-embargo-sjekk (lokal, feiler aldri)
        # ══════════════════════════════════════════════════════════════════════
        embargo_hits: list[tuple[uuid.UUID | None, EmbargoEntry]] = []

        # 1a. Destinasjonsland pa invoice
        dest_entry = check_country(invoice.destination_country)
        if dest_entry:
            logger.info(
                "embargo_hit_destination",
                invoice_id=str(invoice_id),
                country=dest_entry.iso2,
                scope=dest_entry.scope,
            )
            # Bruk forste screenbare entitet som "anker" for resultatet.
            # Dersom ingen entiteter finnes, registrerer vi bare status.
            anchor_id = (
                entities_to_screen[0].id
                if entities_to_screen
                else (all_entities[0].id if all_entities else None)
            )
            embargo_hits.append((anchor_id, dest_entry))

        # 1b. Entiteters land
        for entity in entities_to_screen:
            if entity.country and entity.country != invoice.destination_country:
                entry = check_country(entity.country)
                if entry:
                    logger.info(
                        "embargo_hit_entity",
                        invoice_id=str(invoice_id),
                        entity=entity.name,
                        country=entry.iso2,
                        scope=entry.scope,
                    )
                    embargo_hits.append((entity.id, entry))

        # Lagre embargo-resultater
        for entity_id, entry in embargo_hits:
            status = (
                MatchStatus.CONFIRMED_MATCH
                if entry.scope == "comprehensive"
                else MatchStatus.POTENTIAL_MATCH
            )
            if entity_id is not None:
                sr = _make_embargo_result(invoice_id, entity_id, entry, status)
                screening_records.append(sr)
            all_statuses.append(status)

        # ══════════════════════════════════════════════════════════════════════
        # FASE 1.5 — Intern sperreliste-sjekk (lokal, feiler aldri)
        # ══════════════════════════════════════════════════════════════════════
        try:
            from app.services import internal_watchlist_service as wl_svc
            entity_names = [e.name for e in entities_to_screen if e.name]
            email_addresses = [e.email for e in entities_to_screen if e.email]
            countries = [c for c in [
                invoice.destination_country,
                *[e.country for e in entities_to_screen if e.country],
            ] if c]
            watchlist_hits = await wl_svc.check_invoice(
                session,
                entity_names=entity_names,
                email_addresses=email_addresses,
                countries=countries,
            )
            for hit in watchlist_hits:
                wl_status = (
                    MatchStatus.CONFIRMED_MATCH
                    if hit.severity == "red"
                    else MatchStatus.POTENTIAL_MATCH
                )
                # Finn riktig entity_id for treffet
                hit_entity_id: uuid.UUID | None = None
                for e in entities_to_screen:
                    if hit.entry_type == "name" and e.name and e.name.lower() == hit.matched_value.lower():
                        hit_entity_id = e.id
                        break
                    elif hit.entry_type == "email_domain" and e.email and e.email.lower() == hit.matched_value.lower():
                        hit_entity_id = e.id
                        break
                if hit_entity_id is None and entities_to_screen:
                    hit_entity_id = entities_to_screen[0].id
                if hit_entity_id is None and all_entities:
                    hit_entity_id = all_entities[0].id
                if hit_entity_id is not None:
                    sr = ScreeningResult(
                        id=uuid.uuid4(),
                        invoice_id=invoice_id,
                        entity_id=hit_entity_id,
                        dataset="internal_watchlist",
                        dataset_entity_id=str(hit.entry_id),
                        matched_name=hit.value,
                        score=Decimal("1.0000") if hit.severity == "red" else Decimal("0.8000"),
                        listed_on=None,
                        status=wl_status,
                        raw_response={
                            "watchlist_entry_id": str(hit.entry_id),
                            "entry_type": hit.entry_type,
                            "matched_field": hit.matched_field,
                            "matched_value": hit.matched_value,
                            "reason": hit.reason,
                            "severity": hit.severity,
                        },
                    )
                    screening_records.append(sr)
                    all_statuses.append(wl_status)
                    logger.info(
                        "watchlist_hit",
                        invoice_id=str(invoice_id),
                        entry_type=hit.entry_type,
                        value=hit.value,
                        severity=hit.severity,
                    )
        except Exception:
            logger.exception("internal_watchlist_check_failed", invoice_id=str(invoice_id))

        # ── Heuristikk: trade plausibility (ikke direkte sanksjonstreff) ─────
        plausibility_records = _collect_trade_plausibility_results(
            invoice=invoice,
            entities_to_screen=entities_to_screen,
        )
        for row in plausibility_records:
            screening_records.append(row)
            all_statuses.append(row.status)

        duplicate_records = await _collect_duplicate_invoice_results(
            session=session,
            invoice=invoice,
            entities_to_screen=entities_to_screen,
        )
        for row in duplicate_records:
            screening_records.append(row)
            all_statuses.append(row.status)

        # ══════════════════════════════════════════════════════════════════════
        # FASE 2 — Yente entity-name matching
        # ══════════════════════════════════════════════════════════════════════
        yente_attempted = False
        yente_succeeded = 0

        candidates, primary_by_entity = _build_screening_candidates(
            invoice,
            entities_to_screen,
            all_entities,
        )
        max_candidates = int(getattr(settings, "screening_max_candidates", 60) or 60)
        candidates = _limit_candidates(candidates, max_candidates)
        primary_by_entity = {
            entity_id: cand
            for entity_id, cand in primary_by_entity.items()
            if any(c.entity_id == entity_id and c.key == cand.key for c in candidates)
        }
        await _persist_screening_candidates(
            session=session,
            run=screening_run,
            invoice_id=invoice_id,
            candidates=candidates,
            all_entities=all_entities,
        )

        if candidates:
            yente = get_yente_client()
            yente_is_up = await yente.is_healthy()

            if not yente_is_up:
                logger.warning(
                    "yente_unavailable_skip_name_matching",
                    invoice_id=str(invoice_id),
                )
            else:
                yente_attempted = True
                candidate_dicts = [
                    {
                        "id": c.key,
                        "name": c.name,
                        "entity_type": c.entity_type,
                        "country": c.country,
                    }
                    for c in candidates
                ]

                match_timeout = int(
                    getattr(settings, "screening_match_timeout_seconds", 90) or 90
                )
                try:
                    batch_results = await asyncio.wait_for(
                        yente.match_entities_batch(candidate_dicts),
                        timeout=max(20, match_timeout),
                    )
                except TimeoutError:
                    logger.error(
                        "yente_batch_timeout",
                        invoice_id=str(invoice_id),
                        candidate_count=len(candidate_dicts),
                        timeout_seconds=max(20, match_timeout),
                    )
                    batch_results = {}
                entity_with_match: set[uuid.UUID] = set()
                seen_hits: set[tuple[uuid.UUID, str, str | None, str | None, str]] = set()

                for candidate in candidates:
                    matches: list[YenteMatch] | None = batch_results.get(candidate.key, [])

                    if matches is None:
                        logger.warning(
                            "yente_match_failed_for_candidate",
                            candidate_key=candidate.key,
                            entity_id=str(candidate.entity_id),
                            name=candidate.name,
                            source=candidate.source,
                        )
                        continue

                    yente_succeeded += 1

                    for match in matches:
                        score_dec = Decimal(str(round(match.score, 4)))
                        status = _classify_match(
                            match.score, confirmed_threshold, match_threshold
                        )
                        if status == MatchStatus.CLEAR:
                            continue

                        dedupe_key = (
                            candidate.entity_id,
                            match.dataset,
                            match.entity_id,
                            match.matched_name,
                            status.value,
                        )
                        if dedupe_key in seen_hits:
                            continue
                        seen_hits.add(dedupe_key)

                        raw_payload = dict(match.raw) if match.raw else {}
                        raw_payload["query_source"] = candidate.source
                        raw_payload["query_name"] = candidate.name
                        if candidate.source_email:
                            raw_payload["query_email"] = candidate.source_email

                        sr = ScreeningResult(
                            id=uuid.uuid4(),
                            invoice_id=invoice_id,
                            entity_id=candidate.entity_id,
                            dataset=match.dataset,
                            dataset_entity_id=match.entity_id,
                            matched_name=match.matched_name,
                            score=score_dec,
                            listed_on=match.listed_on,
                            status=status,
                            raw_response=raw_payload or None,
                        )
                        screening_records.append(sr)
                        all_statuses.append(status)
                        entity_with_match.add(candidate.entity_id)

                # Legg inn en "clear" per primær-entity uten treff.
                for entity_id, primary_candidate in primary_by_entity.items():
                    if entity_id in entity_with_match:
                        continue
                    sr = ScreeningResult(
                        id=uuid.uuid4(),
                        invoice_id=invoice_id,
                        entity_id=entity_id,
                        dataset="all",
                        dataset_entity_id=None,
                        matched_name=None,
                        score=Decimal("0.0000"),
                        listed_on=None,
                        status=MatchStatus.CLEAR,
                        raw_response={
                            "query_source": primary_candidate.source,
                            "query_name": primary_candidate.name,
                        },
                    )
                    screening_records.append(sr)
                    all_statuses.append(MatchStatus.CLEAR)

        # ══════════════════════════════════════════════════════════════════════
        # FASE 3 — Lagre og sett compliance_score
        # ══════════════════════════════════════════════════════════════════════
        for sr in screening_records:
            session.add(sr)

        # Dersom yente ble forsøkt men feilet for ALLE entiteter,
        # og vi heller ikke har embargo-treff, er screeningen ufullstendig.
        yente_completely_failed = (
            yente_attempted
            and yente_succeeded == 0
            and not embargo_hits
        )

        if yente_completely_failed and not all_statuses:
            prev_status = invoice.status.value
            invoice.status = InvoiceStatus.SCREENING_FAILED
            invoice.compliance_score = None
            screening_run.status = "failed"
            screening_run.error_message = "Yente svarte ikke for noen kandidater."
            screening_run.finished_at = datetime.now(UTC)
            await append_pipeline_event(
                session,
                invoice_id=invoice.id,
                stage="screening",
                action="failed",
                status_from=prev_status,
                status_to=InvoiceStatus.SCREENING_FAILED.value,
                message=screening_run.error_message,
            )
            await session.commit()
            logger.error(
                "screening_aborted_yente_all_failed",
                invoice_id=str(invoice_id),
            )
            return invoice

        # Dersom ingen entiteter og ingen destinasjonsland: GREEN
        if not all_statuses:
            invoice.compliance_score = ComplianceScore.GREEN
        else:
            invoice.compliance_score = _worst_compliance(all_statuses)

        prev_status = invoice.status.value
        invoice.status = InvoiceStatus.SCREENED
        screening_run.status = "completed"
        screening_run.error_message = None
        screening_run.finished_at = datetime.now(UTC)
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="screening",
            action="completed",
            status_from=prev_status,
            status_to=InvoiceStatus.SCREENED.value,
            payload={
                "compliance_score": invoice.compliance_score.value if invoice.compliance_score else None,
                "embargo_hits": len(embargo_hits),
                "yente_results": yente_succeeded,
                "record_count": len(screening_records),
            },
        )

        # ── Audit-logg for screening ──────────────────────────────────────────
        confirmed_hits = sum(1 for s in all_statuses if s == MatchStatus.CONFIRMED_MATCH)
        potential_hits = sum(1 for s in all_statuses if s == MatchStatus.POTENTIAL_MATCH)
        await audit_service.log(
            session,
            action="screening.completed",
            invoice_id=invoice.id,
            details={
                "compliance_score": invoice.compliance_score.value if invoice.compliance_score else None,
                "embargo_hits": len(embargo_hits),
                "confirmed_matches": confirmed_hits,
                "potential_matches": potential_hits,
                "record_count": len(screening_records),
                "candidate_count": len(candidates),
            },
        )

        # ── In-app varsel for forhøyet score ─────────────────────────────────
        score_val = invoice.compliance_score.value if invoice.compliance_score else "green"
        if score_val in ("yellow", "red"):
            from app.services import notification_service
            score_label = "🔴 Rød" if score_val == "red" else "🟡 Gul"
            inv_label = invoice.original_filename or invoice.invoice_number or str(invoice.id)[:8]
            await notification_service.create(
                session,
                message=f"{score_label} compliance-score: {inv_label} — krever manuell review",
                level="error" if score_val == "red" else "warn",
                invoice_id=invoice.id,
                target_roles=["compliance_officer", "admin"],
            )

        # ── Regelmotor — evaluer alle aktive YAML-regler ──────────────────────
        # all_entities er allerede hentet ovenfor; lines lastes her for regelmotor.
        from sqlalchemy import select as _select
        from app.models.invoice_line import InvoiceLine as _InvoiceLine
        lines_result = await session.execute(
            _select(_InvoiceLine).where(_InvoiceLine.invoice_id == invoice_id)
        )
        invoice_lines = list(lines_result.scalars().all())

        try:
            rule_results = await rule_engine_service.evaluate_invoice(
                session,
                invoice,
                entities=list(all_entities),
                lines=invoice_lines,
                write_audit=True,
            )
            triggered = [r for r in rule_results if r.triggered]
            if triggered:
                # Hvis en regel trigges med høyere alvorlighet enn nåværende score,
                # eskalér compliance_score.
                severity_map = {"red": ComplianceScore.RED, "yellow": ComplianceScore.YELLOW}
                for r in triggered:
                    escalated = severity_map.get(r.severity)
                    if escalated and (
                        invoice.compliance_score == ComplianceScore.GREEN
                        or (invoice.compliance_score == ComplianceScore.YELLOW and escalated == ComplianceScore.RED)
                    ):
                        invoice.compliance_score = escalated
                logger.info(
                    "rules_evaluated",
                    invoice_id=str(invoice_id),
                    total=len(rule_results),
                    triggered=len(triggered),
                )
        except Exception:
            logger.exception("rule_engine_failed", invoice_id=str(invoice_id))
            # Regelmotor-feil er ikke fatalt — screening fortsetter

        await session.commit()

        logger.info(
            "screening_completed",
            invoice_id=str(invoice_id),
            compliance_score=invoice.compliance_score.value,
            embargo_hits=len(embargo_hits),
            yente_results=yente_succeeded,
            total_records=len(screening_records),
        )
        return invoice

    except Exception as exc:
        logger.error(
            "screening_failed",
            invoice_id=str(invoice_id),
            error=str(exc),
            exc_info=True,
        )
        try:
            prev_status = invoice.status.value
            invoice.status = InvoiceStatus.SCREENING_FAILED
            invoice.compliance_score = None
            if screening_run is not None:
                screening_run.status = "failed"
                screening_run.error_message = str(exc)[:2000]
                screening_run.finished_at = datetime.now(UTC)
            await append_pipeline_event(
                session,
                invoice_id=invoice.id,
                stage="screening",
                action="failed",
                status_from=prev_status,
                status_to=InvoiceStatus.SCREENING_FAILED.value,
                message=str(exc)[:2000],
            )
            await session.commit()
        except Exception:
            await session.rollback()
        raise


async def get_screening_results(
    session: AsyncSession,
    invoice_id: uuid.UUID,
) -> list[ScreeningResult]:
    """Hent alle screeningresultater for en invoice, nyeste forst."""
    result = await session.execute(
        select(ScreeningResult)
        .where(ScreeningResult.invoice_id == invoice_id)
        .order_by(ScreeningResult.screened_at.desc(), ScreeningResult.score.desc())
    )
    return list(result.scalars().all())


async def _persist_screening_candidates(
    *,
    session: AsyncSession,
    run: ScreeningRun,
    invoice_id: uuid.UUID,
    candidates: list[_ScreeningCandidate],
    all_entities: list[Entity],
) -> None:
    entity_map = {entity.id: entity for entity in all_entities}
    for candidate in candidates:
        entity = entity_map.get(candidate.entity_id)
        row = ScreeningCandidate(
            run_id=run.id,
            invoice_id=invoice_id,
            entity_id=candidate.entity_id,
            entity_name=entity.name if entity else None,
            entity_role=entity.role.value if entity else None,
            candidate_name=candidate.name,
            entity_type=candidate.entity_type,
            country=candidate.country,
            source=candidate.source,
            source_email=candidate.source_email,
            is_primary=candidate.primary,
        )
        session.add(row)

    run.candidate_count = len(candidates)
    await session.flush()


async def get_latest_screening_run(
    session: AsyncSession,
    invoice_id: uuid.UUID,
) -> ScreeningRun | None:
    result = await session.execute(
        select(ScreeningRun)
        .where(ScreeningRun.invoice_id == invoice_id)
        .order_by(ScreeningRun.started_at.desc())
        .limit(1)
    )
    return result.scalars().first()


async def get_screening_candidates_from_run(
    session: AsyncSession,
    run_id: uuid.UUID,
) -> list[ScreeningCandidate]:
    result = await session.execute(
        select(ScreeningCandidate)
        .where(ScreeningCandidate.run_id == run_id)
        .order_by(
            ScreeningCandidate.entity_name.asc(),
            ScreeningCandidate.source.asc(),
            ScreeningCandidate.candidate_name.asc(),
        )
    )
    return list(result.scalars().all())


async def get_screening_candidates_preview(
    session: AsyncSession,
    invoice_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Bygg og returner kandidater som brukes av screeningmotoren."""
    invoice = await session.get(Invoice, invoice_id)
    if not invoice:
        raise ValueError(f"Invoice {invoice_id} finnes ikke")

    result = await session.execute(
        select(Entity).where(Entity.invoice_id == invoice_id)
    )
    all_entities = result.scalars().all()
    entities_to_screen = [e for e in all_entities if e.role in _SCREENED_ROLES]
    entity_map = {entity.id: entity for entity in all_entities}

    candidates, _primary = _build_screening_candidates(
        invoice,
        entities_to_screen,
        all_entities,
    )

    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        entity = entity_map.get(candidate.entity_id)
        rows.append(
            {
                "key": candidate.key,
                "entity_id": candidate.entity_id,
                "entity_name": entity.name if entity else None,
                "entity_role": entity.role.value if entity else None,
                "candidate_name": candidate.name,
                "entity_type": candidate.entity_type,
                "country": candidate.country,
                "source": candidate.source,
                "source_email": candidate.source_email,
                "primary": candidate.primary,
            }
        )

    rows.sort(
        key=lambda row: (
            str(row.get("entity_name") or ""),
            str(row.get("source") or ""),
            str(row.get("candidate_name") or ""),
        )
    )
    return rows
