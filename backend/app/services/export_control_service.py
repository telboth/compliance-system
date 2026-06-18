"""Eksportkontroll-tjeneste — matcher fakturalinjer mot DEKSAs varelister.

Tre matchere med fallende konfidens kjøres mot hver fakturalinje:

  1. ECCN/ML strukturmatch (HØY)    — eksplisitt kontrollkode på linjen
                                       (line.eccn) eller i beskrivelsen.
  2. HS-kode-bro (MEDIUM)           — gjenbruker hs_code_service for å se
                                       om varens tolltariff indikerer kontroll.
  3. Nøkkelord i beskrivelse (LAV)  — kuratert leksikon per listekategori.

Resultatet kobles til compliance_score med destinasjonsbevisst logikk:
  - Vareliste I (militært) med eksplisitt ML-kode  → RØD (controlled)
  - Vareliste II (dual-use) med eksplisitt ECCN     → RØD hvis embargo-/
                                                       sanksjonert destinasjon,
                                                       ellers GUL (review)
  - Kun HS-/nøkkelord-treff                          → GUL (review)
  - Ingen treff                                      → GRØNN (clear)

VIKTIG: Dette er beslutningsstøtte, ikke en juridisk avgjørelse. Endelig
kontrollstatus krever eksportørens tekniske egenvurdering mot lista.
Se app/data/export_control_reference.py for kildehenvisninger.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.data import export_control_reference as ref
from app.models.export_control_item import ExportControlListItem
from app.models.invoice import ComplianceScore, Invoice, InvoiceStatus
from app.sanctions import embargo
from app.services.hs_code_service import classify as classify_hs

# Kontrollkode-mønster for å finne ECCN/ML inne i fritekstbeskrivelse
_CODE_IN_TEXT_RE = re.compile(r"\b(ML\s?\d{1,2}|[0-9][A-E]\d{3})\b", re.IGNORECASE)

_STATUS_CLEAR = "clear"
_STATUS_REVIEW = "review"
_STATUS_CONTROLLED = "controlled"


# ── Resultat-dataklasser ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class ExportControlLineHit:
    """Ett listematch-treff på én fakturalinje."""

    line_index: int
    line_description: str | None
    matched_value: str           # koden/nøkkelordet som matchet
    list_code: str               # "I" | "II"
    category: str                # "ML10" | "6" | "HS:85"
    category_title: str          # norsk kategoritittel
    item_code: str | None        # fullt kontrollnummer hvis strukturelt match
    confidence: str              # "high" | "medium" | "low"
    matched_via: str             # "eccn" | "hs" | "keyword"
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "line_index": self.line_index,
            "line_description": self.line_description,
            "matched_value": self.matched_value,
            "list_code": self.list_code,
            "category": self.category,
            "category_title": self.category_title,
            "item_code": self.item_code,
            "confidence": self.confidence,
            "matched_via": self.matched_via,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ExportControlCheckResult:
    """Samlet eksportkontroll-vurdering for én faktura."""

    flagged: bool
    status: str                  # "clear" | "review" | "controlled"
    severity: str                # "green" | "yellow" | "red"
    destination_country: str | None
    destination_sanctioned: bool
    hits: list[ExportControlLineHit] = field(default_factory=list)
    summary: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "flagged": self.flagged,
            "status": self.status,
            "severity": self.severity,
            "destination_country": self.destination_country,
            "destination_sanctioned": self.destination_sanctioned,
            "hits": [h.to_dict() for h in self.hits],
            "summary": self.summary,
        }


# ── Per-linje matching ────────────────────────────────────────────────────────


def _structural_hit(
    line_index: int,
    description: str | None,
    code: str,
    matched_value: str,
) -> ExportControlLineHit | None:
    """Bygg et treff fra en strukturelt tolket kontrollkode."""
    sm = ref.parse_control_code(code)
    if sm is None:
        return None
    cat = sm.category_ref
    if sm.list_code == "I":
        reason = (
            f"Eksplisitt militær kontrollkode {sm.normalized_code} "
            f"(Vareliste I, {sm.category}) på fakturalinjen."
        )
    else:
        reason = (
            f"Eksplisitt dual-use kontrollkode {sm.normalized_code} "
            f"(Vareliste II, kategori {sm.category}) på fakturalinjen."
        )
    return ExportControlLineHit(
        line_index=line_index,
        line_description=description,
        matched_value=matched_value,
        list_code=sm.list_code,
        category=sm.category,
        category_title=cat.title_no if cat else sm.category,
        item_code=sm.normalized_code,
        confidence="high",
        matched_via="eccn",
        reason=reason,
    )


def _hs_hit(line_index: int, description: str | None, hs_code: str) -> ExportControlLineHit | None:
    """Bygg et treff fra HS-kode-broen (medium konfidens)."""
    cls = classify_hs(hs_code)
    if cls is None or not cls.is_controlled:
        return None
    # Kapittel 93 (våpen) og 36 (eksplosiver) indikerer Vareliste I; ellers dual-use.
    list_code = "I" if cls.chapter in {"93", "36"} else "II"
    title = cls.heading_description or cls.chapter_description
    return ExportControlLineHit(
        line_index=line_index,
        line_description=description,
        matched_value=cls.code,
        list_code=list_code,
        category=f"HS:{cls.heading or cls.chapter}",
        category_title=title,
        item_code=None,
        confidence="medium",
        matched_via="hs",
        reason=(
            f"HS-kode {cls.code} ({title}) er kontrollert/dual-use-relevant — "
            f"{cls.risk_reason or 'krever vurdering mot vareliste'}."
        ),
    )


def _keyword_hits(line_index: int, description: str | None) -> list[ExportControlLineHit]:
    """Bygg treff fra nøkkelord i linjebeskrivelsen (lav konfidens)."""
    hits: list[ExportControlLineHit] = []
    for kw, cat in ref.keyword_matches(description):
        hits.append(
            ExportControlLineHit(
                line_index=line_index,
                line_description=description,
                matched_value=kw,
                list_code=cat.list_code,
                category=cat.category,
                category_title=cat.title_no,
                item_code=None,
                confidence="low",
                matched_via="keyword",
                reason=(
                    f"Beskrivelsen inneholder «{kw}», som kan indikere "
                    f"{'Vareliste I' if cat.list_code == 'I' else 'Vareliste II'} "
                    f"({cat.title_no}). Krever egenvurdering."
                ),
            )
        )
    return hits


_CONF_RANK = {"high": 3, "medium": 2, "low": 1}


def _match_line(line_index: int, line) -> list[ExportControlLineHit]:
    """Match én fakturalinje med alle tre matcherne, dedupliser per kategori."""
    description = getattr(line, "description", None)
    candidates: list[ExportControlLineHit] = []

    # 1. Strukturmatch på eksplisitt ECCN-felt
    eccn = getattr(line, "eccn", None)
    if eccn:
        hit = _structural_hit(line_index, description, eccn, eccn)
        if hit:
            candidates.append(hit)

    # 1b. Strukturmatch på kode funnet i beskrivelse (f.eks. "ECCN 6A001")
    if description:
        for m in _CODE_IN_TEXT_RE.findall(description):
            hit = _structural_hit(line_index, description, m, m)
            if hit:
                candidates.append(hit)

    # 2. HS-kode-broen
    hs = getattr(line, "hs_code", None)
    if hs:
        hit = _hs_hit(line_index, description, hs)
        if hit:
            candidates.append(hit)

    # 3. Nøkkelord
    candidates.extend(_keyword_hits(line_index, description))

    # Dedupliser: behold sterkeste treff per (list_code, category)
    best: dict[tuple[str, str], ExportControlLineHit] = {}
    for h in candidates:
        key = (h.list_code, h.category)
        cur = best.get(key)
        if cur is None or _CONF_RANK[h.confidence] > _CONF_RANK[cur.confidence]:
            best[key] = h
    return list(best.values())


# ── Faktura-evaluering (ren, synkron — brukes ved read-time) ───────────────────


def _normalize_country(c: str | None) -> str | None:
    if not c:
        return None
    c = c.strip().upper()
    return c[:2] if c else None


def evaluate_invoice_export_control(
    invoice: Invoice,
    lines: list | None = None,
) -> ExportControlCheckResult:
    """Vurder en faktura mot varelistene basert på linjene.

    Ren funksjon (ingen DB/nettverk) slik at den kan kalles ved read-time,
    på linje med VAT-sjekken.

    ``lines`` kan oppgis eksplisitt for å unngå lazy-loading i async
    SQLAlchemy (brukes fra screening). Hvis None brukes ``invoice.lines``,
    som krever at relasjonen er eager-lastet.
    """
    hits: list[ExportControlLineHit] = []
    line_list = lines if lines is not None else list(getattr(invoice, "lines", []) or [])
    for idx, line in enumerate(line_list):
        hits.extend(_match_line(idx, line))

    dest = _normalize_country(invoice.destination_country)
    dest_sanctioned = embargo.is_sanctioned(dest)

    if not hits:
        return ExportControlCheckResult(
            flagged=False,
            status=_STATUS_CLEAR,
            severity="green",
            destination_country=dest,
            destination_sanctioned=dest_sanctioned,
            hits=[],
            summary=None,
        )

    has_explicit_military = any(
        h.list_code == "I" and h.confidence == "high" for h in hits
    )
    has_explicit_dual_use = any(
        h.list_code == "II" and h.confidence == "high" for h in hits
    )

    if has_explicit_military:
        status, severity = _STATUS_CONTROLLED, "red"
    elif has_explicit_dual_use and dest_sanctioned:
        status, severity = _STATUS_CONTROLLED, "red"
    else:
        # Eksplisitt dual-use til ordinær destinasjon, eller kun HS/nøkkelord
        status, severity = _STATUS_REVIEW, "yellow"

    summary = _build_summary(hits, status, dest, dest_sanctioned)

    return ExportControlCheckResult(
        flagged=True,
        status=status,
        severity=severity,
        destination_country=dest,
        destination_sanctioned=dest_sanctioned,
        hits=hits,
        summary=summary,
    )


def _build_summary(
    hits: list[ExportControlLineHit],
    status: str,
    dest: str | None,
    dest_sanctioned: bool,
) -> str:
    """Kort oppsummering for visning i lister (≤512 tegn)."""
    list_i = sorted({h.category for h in hits if h.list_code == "I"})
    list_ii = sorted({h.category for h in hits if h.list_code == "II"})
    parts: list[str] = []
    if list_i:
        parts.append(f"Vareliste I: {', '.join(list_i)}")
    if list_ii:
        # Filtrer bort HS:-pseudokategorier fra hovedteksten for lesbarhet
        real = [c for c in list_ii if not c.startswith("HS:")]
        shown = real or list_ii
        parts.append(f"Vareliste II: kat. {', '.join(shown)}")
    base = "; ".join(parts) if parts else "Mulig listeført vare"
    if status == _STATUS_CONTROLLED:
        prefix = "🔴 Kontrollert vare"
        if dest_sanctioned and dest:
            prefix += f" til sanksjonert/embargoland ({dest})"
    else:
        prefix = "🟡 Mulig lisenspliktig — krever egenvurdering"
    return f"{prefix} — {base}"[:512]


# ── Worklist-spørringer ───────────────────────────────────────────────────────


async def list_export_control_invoices(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    flagged_only: bool = True,
    list_filter: str | None = None,
    status_filter: str | None = None,
) -> tuple[list[ExportControlCheckResult], list[Invoice], int, int]:
    """Hent fakturaer med eksportkontroll-vurdering for arbeidslista.

    Bruker lagret ``export_control_status`` for databasefiltrering/-paginering,
    og beregner full detalj ved read-time per side.

    Returnerer (results, invoices, total_flagged, total_scanned) i samme
    rekkefølge slik at API-laget kan koble dem sammen.
    """
    total_scanned: int = (
        await session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.export_control_status.is_not(None))
        )
    ).scalar_one()

    total_flagged: int = (
        await session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.export_control_status.in_([_STATUS_REVIEW, _STATUS_CONTROLLED]))
        )
    ).scalar_one()

    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.lines), selectinload(Invoice.entities))
        .order_by(Invoice.created_at.desc())
    )
    if flagged_only:
        stmt = stmt.where(Invoice.export_control_status.in_([_STATUS_REVIEW, _STATUS_CONTROLLED]))
    else:
        stmt = stmt.where(Invoice.export_control_status.is_not(None))
    if status_filter in {_STATUS_REVIEW, _STATUS_CONTROLLED, _STATUS_CLEAR}:
        stmt = stmt.where(Invoice.export_control_status == status_filter)

    stmt = stmt.limit(limit).offset(offset)
    invoices = list((await session.execute(stmt)).scalars().all())

    results: list[ExportControlCheckResult] = []
    kept: list[Invoice] = []
    for inv in invoices:
        res = evaluate_invoice_export_control(inv)
        if list_filter in {"I", "II"} and not any(h.list_code == list_filter for h in res.hits):
            continue
        results.append(res)
        kept.append(inv)

    return results, kept, total_flagged, total_scanned


# ── Referanseliste-oppslag (DB-importert fullversjon) ─────────────────────────


def normalize_item_code(code: str) -> str:
    """Normaliser et kontrollnummer for oppslag (uten punktum/mellomrom, uppercase)."""
    return re.sub(r"[\s.\-]", "", code or "").upper()


# Bakoverkompatibelt internt alias
_normalize_code = normalize_item_code


async def upsert_item(
    session: AsyncSession,
    *,
    list_code: str,
    category: str,
    group: str | None,
    item_code: str,
    title: str | None,
    regime: str | None,
    source_version: str,
) -> bool:
    """Sett inn eller oppdater ett listepunkt. Returnerer True hvis nytt.

    Idempotent på (item_code_normalized, source_version).
    """
    norm = normalize_item_code(item_code)
    existing = (
        await session.execute(
            select(ExportControlListItem).where(
                ExportControlListItem.item_code_normalized == norm,
                ExportControlListItem.source_version == source_version,
            )
        )
    ).scalars().first()
    if existing is not None:
        existing.list_code = list_code
        existing.category = category.upper()
        existing.group = group
        existing.item_code = item_code
        existing.title = title
        existing.regime = regime
        return False
    session.add(
        ExportControlListItem(
            list_code=list_code,
            category=category.upper(),
            group=group,
            item_code=item_code,
            item_code_normalized=norm,
            title=title,
            regime=regime,
            source_version=source_version,
        )
    )
    return True


async def seed_reference_categories(session: AsyncSession) -> int:
    """Seed kategori-baselinen fra den statiske referansen (source 'deksa-seed').

    Gjør at referanse-UI og worklist har innhold før den fulle EU-Excel-lista
    importeres. Returnerer antall nye rader.
    """
    created = 0
    for cat in ref.ALL_CATEGORIES:
        is_new = await upsert_item(
            session,
            list_code=cat.list_code,
            category=cat.category,
            group=cat.category[1:] if cat.list_code == "II" and len(cat.category) > 1 else None,
            item_code=cat.category if cat.list_code == "I" else f"Kat. {cat.category}",
            title=f"{cat.title_no} / {cat.title_en}",
            regime=cat.regime,
            source_version="deksa-seed",
        )
        created += int(is_new)
    return created


async def lookup_item_title(session: AsyncSession, code: str) -> str | None:
    """Slå opp eksakt tittel for et kontrollnummer fra den importerte lista."""
    norm = _normalize_code(code)
    if not norm:
        return None
    row = (
        await session.execute(
            select(ExportControlListItem.title)
            .where(ExportControlListItem.item_code_normalized == norm)
            .limit(1)
        )
    ).scalars().first()
    return row


async def browse_items(
    session: AsyncSession,
    *,
    list_code: str | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ExportControlListItem], int]:
    """Bla i den importerte varelista (for referanse-UI)."""
    base = select(ExportControlListItem)
    if list_code:
        base = base.where(ExportControlListItem.list_code == list_code)
    if category:
        base = base.where(ExportControlListItem.category == category.upper())
    if search:
        term = search.strip()
        norm = _normalize_code(term)
        base = base.where(
            or_(
                ExportControlListItem.item_code_normalized.ilike(f"%{norm}%"),
                ExportControlListItem.title.ilike(f"%{term}%"),
            )
        )

    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    rows = list(
        (
            await session.execute(
                base.order_by(ExportControlListItem.item_code_normalized.asc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return rows, total


async def count_items(session: AsyncSession) -> int:
    """Antall importerte listepunkter — brukes for å vise om lista er lastet."""
    return (
        await session.execute(select(func.count()).select_from(ExportControlListItem))
    ).scalar_one()


# ── Backfill av eksisterende fakturaer ────────────────────────────────────────

# Fakturaer som har vært gjennom screening (export_control_status settes ved
# screening; backfill dekker fakturaer screenet før funksjonen fantes).
_SCREENED_STATUSES = (
    InvoiceStatus.SCREENED,
    InvoiceStatus.REVIEWED,
    InvoiceStatus.APPROVED,
    InvoiceStatus.BLOCKED,
)


async def backfill_export_control(
    session: AsyncSession,
    *,
    rescore: bool = True,
    batch_size: int = 200,
) -> dict[str, int]:
    """Beregn eksportkontroll-status for alle allerede screenede fakturaer.

    Setter ``export_control_status`` + ``export_control_summary`` slik at
    arbeidslista fylles for historiske fakturaer. Når ``rescore`` er sann
    eskaleres også ``compliance_score`` — men kun for fakturaer som ennå
    ikke har en manuell review-beslutning, slik at historiske utfall bevares.

    Returnerer {processed, flagged, rescored}.
    """
    processed = flagged = rescored = 0
    offset = 0
    while True:
        rows = list(
            (
                await session.execute(
                    select(Invoice)
                    .options(selectinload(Invoice.lines))
                    .where(Invoice.status.in_(_SCREENED_STATUSES))
                    .order_by(Invoice.created_at.asc())
                    .limit(batch_size)
                    .offset(offset)
                )
            )
            .scalars()
            .all()
        )
        if not rows:
            break
        for inv in rows:
            res = evaluate_invoice_export_control(inv)
            inv.export_control_status = res.status
            inv.export_control_summary = res.summary
            processed += 1
            if res.flagged:
                flagged += 1
            if rescore and inv.review_decision is None:
                esc = {"red": ComplianceScore.RED, "yellow": ComplianceScore.YELLOW}.get(
                    res.severity
                )
                if esc and (
                    inv.compliance_score == ComplianceScore.GREEN
                    or (
                        inv.compliance_score == ComplianceScore.YELLOW
                        and esc == ComplianceScore.RED
                    )
                ):
                    inv.compliance_score = esc
                    rescored += 1
        await session.commit()
        offset += batch_size

    return {"processed": processed, "flagged": flagged, "rescored": rescored}


def classify_code(code: str) -> dict[str, object] | None:
    """Klassifiser et enkelt kontrollnummer strukturelt (ingen DB)."""
    sm = ref.parse_control_code(code)
    if sm is None:
        return None
    cat = sm.category_ref
    return {
        "input": code,
        "normalized_code": sm.normalized_code,
        "list_code": sm.list_code,
        "category": sm.category,
        "group": sm.group,
        "category_title_no": cat.title_no if cat else None,
        "category_title_en": cat.title_en if cat else None,
        "regime": cat.regime if cat else None,
    }
