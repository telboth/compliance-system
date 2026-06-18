"""Catch-all-tjeneste — sluttbruker- og sluttbruk-screening (tredje ben i eksportkontroll).

DEKSAs «catch-all» (kontroll av varer utenfor listene): selv varer som IKKE
står på Vareliste I/II kan kreve lisens dersom de er ment for — eller det er
risiko for at de havner i — sensitiv sluttbruk eller hos en sensitiv sluttbruker
(militær, kjernefysisk, masseødeleggelsesvåpen) eller en embargo-destinasjon.

Mens varelistematchen (export_control_service) svarer på *hva* varen er, svarer
denne tjenesten på *hvem som skal bruke den og til hva*. Signalene er klassiske
eksportkontroll-«røde flagg» (jf. BIS/EU Know-Your-Customer-veiledning):

  - Sluttbruker eller destinasjon under embargo
  - Militær / kjernefysisk / forsknings-sluttbruker
  - Sensitiv sluttbruk (militær/WMD) i instruksjoner/kommentarer
  - Diversjonsrisiko: mellomledd som sluttbruker, eller destinasjonsland ≠
    sluttbrukerland mot høyrisiko
  - Udeklarert sluttbruker ved eksport til høyrisikoland

VIKTIG: Beslutningsstøtte, ikke en juridisk avgjørelse. Endelig vurdering
krever eksportørens egenvurdering og evt. sluttbrukererklæring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entity import EntityRole
from app.models.invoice import ComplianceScore, Invoice, InvoiceStatus
from app.sanctions import embargo

_STATUS_CLEAR = "clear"
_STATUS_REVIEW = "review"
_STATUS_CONTROLLED = "controlled"

# Roller som representerer "mottaker-/sluttbrukersiden", i prioritert rekkefølge.
_END_USER_ROLES = (
    EntityRole.END_USER,
    EntityRole.CONSIGNEE,
    EntityRole.DELIVERY_ADDRESS,
    EntityRole.BUYER,
)


# ── Leksikon ──────────────────────────────────────────────────────────────────
# Ordgrense-matching brukes for å unngå delstreng-falske positiver.

_MILITARY_KEYWORDS = (
    "ministry of defence", "ministry of defense", "department of defense",
    "armed forces", "air force", "naval", "navy", "army", "military",
    "defence", "defense", "arsenal", "ordnance", "munitions", "artillery",
    "rocket force", "missile", "military academy", "defence research",
    "forsvaret", "forsvarsdepartement", "försvarsmakten",
)
_NUCLEAR_KEYWORDS = (
    "nuclear", "atomic energy", "enrichment", "isotope", "reactor",
    "centrifuge", "radiochemical", "fissile", "uranium", "plutonium",
)
_RESEARCH_KEYWORDS = (
    "academy of sciences", "national laboratory", "research institute",
    "scientific research", "institute of physics", "missile research",
    "defence research", "aerospace research",
)
_SENSITIVE_END_USE_KEYWORDS = (
    "military use", "military application", "military end-use", "for the army",
    "for the navy", "for the air force", "weapon", "weapons system",
    "defence application", "defense application", "naval application",
    "warhead", "missile", "ballistic", "uav", "unmanned aerial",
    "nuclear", "enrichment", "reactor", "centrifuge", "proliferation",
)
# Mellomledd/diversjonsindikatorer i sluttbrukernavn
_BROKER_KEYWORDS = (
    "freight forward", "forwarding", "logistics", "general trading",
    "trading company", "trading co", "trading llc", "import export",
    "import-export", "distributor", "reseller", "intermediary",
)


def _kw_hit(text: str | None, keywords: tuple[str, ...]) -> str | None:
    """Returner første nøkkelord med ordgrense-treff i ``text``, ellers None."""
    if not text:
        return None
    hay = text.lower()
    for kw in keywords:
        if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", hay):
            return kw
    return None


# ── Resultat-dataklasser ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class CatchAllSignal:
    """Ett røde-flagg-signal i catch-all-vurderingen."""

    signal_type: str   # embargoed_end_user | military_end_user | nuclear_end_user |
    #                    sensitive_end_use | diversion_risk | undeclared_end_user
    severity: str      # "yellow" | "red"
    title: str
    detail: str
    entity_name: str | None = None
    country: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "signal_type": self.signal_type,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "entity_name": self.entity_name,
            "country": self.country,
        }


@dataclass(frozen=True)
class CatchAllCheckResult:
    flagged: bool
    status: str             # clear | review | controlled
    severity: str           # green | yellow | red
    end_user_name: str | None
    end_user_country: str | None
    destination_country: str | None
    signals: list[CatchAllSignal] = field(default_factory=list)
    summary: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "flagged": self.flagged,
            "status": self.status,
            "severity": self.severity,
            "end_user_name": self.end_user_name,
            "end_user_country": self.end_user_country,
            "destination_country": self.destination_country,
            "signals": [s.to_dict() for s in self.signals],
            "summary": self.summary,
        }


# ── Hjelp ─────────────────────────────────────────────────────────────────────


def _normalize_country(c: str | None) -> str | None:
    if not c:
        return None
    c = c.strip().upper()
    return c[:2] if c else None


def _country_risk(c: str | None) -> str:
    """'high' (comprehensive embargo) | 'elevated' (sektor) | 'normal'."""
    entry = embargo.check_country(c)
    if entry is None:
        return "normal"
    return "high" if entry.scope == "comprehensive" else "elevated"


def _pick_end_user(entities: list) -> object | None:
    """Velg den mest relevante mottaker-/sluttbrukerentiteten."""
    for role in _END_USER_ROLES:
        for e in entities:
            if getattr(e, "role", None) == role:
                return e
    return None


# ── Evaluering (ren, synkron — brukes ved read-time) ──────────────────────────


def evaluate_invoice_catch_all(
    invoice: Invoice,
    entities: list | None = None,
    lines: list | None = None,
) -> CatchAllCheckResult:
    """Vurder en faktura for catch-all-/sluttbrukerrisiko.

    Ren funksjon (ingen DB/nettverk). ``entities``/``lines`` kan oppgis
    eksplisitt for å unngå lazy-loading i async SQLAlchemy.
    """
    ent_list = entities if entities is not None else list(getattr(invoice, "entities", []) or [])
    line_list = lines if lines is not None else list(getattr(invoice, "lines", []) or [])

    dest = _normalize_country(invoice.destination_country)
    end_user = _pick_end_user(ent_list)
    eu_name = getattr(end_user, "name", None) if end_user else None
    eu_country = _normalize_country(getattr(end_user, "country", None)) if end_user else None

    # Land med høyest risiko av destinasjon og sluttbrukerland
    dest_risk = _country_risk(dest)
    eu_risk = _country_risk(eu_country)
    worst_country_risk = "high" if "high" in (dest_risk, eu_risk) else (
        "elevated" if "elevated" in (dest_risk, eu_risk) else "normal"
    )
    any_sanctioned = embargo.is_sanctioned(dest) or embargo.is_sanctioned(eu_country)

    signals: list[CatchAllSignal] = []

    # 1. Sluttbruker/destinasjon under totalembargo
    if embargo.is_comprehensive_embargo(eu_country) or embargo.is_comprehensive_embargo(dest):
        c = eu_country if embargo.is_comprehensive_embargo(eu_country) else dest
        signals.append(
            CatchAllSignal(
                signal_type="embargoed_end_user",
                severity="red",
                title="Sluttbruker/destinasjon under totalembargo",
                detail=(
                    f"Land {c} er under totalembargo — eksport er forbudt/"
                    "lisenspliktig uansett vare."
                ),
                entity_name=eu_name,
                country=c,
            )
        )

    # 2. Militær sluttbruker
    mil = _kw_hit(eu_name, _MILITARY_KEYWORDS)
    if mil:
        sev = "red" if any_sanctioned else "yellow"
        signals.append(
            CatchAllSignal(
                signal_type="military_end_user",
                severity=sev,
                title="Mulig militær sluttbruker",
                detail=(
                    f"Sluttbrukernavn inneholder «{mil}» — kan indikere "
                    "militær sluttbruk (catch-all)."
                ),
                entity_name=eu_name,
                country=eu_country,
            )
        )

    # 3. Kjernefysisk sluttbruker
    nuc = _kw_hit(eu_name, _NUCLEAR_KEYWORDS) or _kw_hit(eu_name, _RESEARCH_KEYWORDS)
    if nuc:
        sev = "red" if worst_country_risk == "high" else "yellow"
        signals.append(
            CatchAllSignal(
                signal_type="nuclear_end_user",
                severity=sev,
                title="Sensitiv sluttbruker (kjernefysisk/forskning)",
                detail=(
                    f"Sluttbrukernavn inneholder «{nuc}» — mulig "
                    "kjernefysisk/forsknings-sluttbruk."
                ),
                entity_name=eu_name,
                country=eu_country,
            )
        )

    # 4. Sensitiv sluttbruk i instruksjoner/kommentarer/linjer
    use_text = " ".join(
        filter(
            None,
            [
                getattr(invoice, "instructions", None),
                getattr(invoice, "comments", None),
                getattr(invoice, "po_number", None),
                *[getattr(ln, "description", None) for ln in line_list],
            ],
        )
    )
    use_hit = _kw_hit(use_text, _SENSITIVE_END_USE_KEYWORDS)
    if use_hit:
        sev = "red" if any_sanctioned else "yellow"
        signals.append(
            CatchAllSignal(
                signal_type="sensitive_end_use",
                severity=sev,
                title="Sensitiv sluttbruk angitt",
                detail=f"Dokumentteksten nevner «{use_hit}» — mulig militær/WMD-sluttbruk.",
                entity_name=eu_name,
                country=dest,
            )
        )

    # 5. Diversjonsrisiko: mellomledd som sluttbruker mot høyrisiko
    broker = _kw_hit(eu_name, _BROKER_KEYWORDS)
    if broker and worst_country_risk in ("high", "elevated"):
        signals.append(
            CatchAllSignal(
                signal_type="diversion_risk",
                severity="yellow",
                title="Diversjonsrisiko — mellomledd som sluttbruker",
                detail=(
                    f"Sluttbruker fremstår som mellomledd («{broker}») mot "
                    "høyrisiko-destinasjon — risiko for videreeksport."
                ),
                entity_name=eu_name,
                country=eu_country or dest,
            )
        )

    # 6. Destinasjon ≠ sluttbrukerland mot sanksjonert land (mulig re-eksport)
    if (
        dest and eu_country and dest != eu_country
        and (embargo.is_sanctioned(dest) or embargo.is_sanctioned(eu_country))
    ):
        signals.append(
            CatchAllSignal(
                signal_type="diversion_risk",
                severity="yellow",
                title="Mulig re-eksport / diversjon",
                detail=(
                    f"Destinasjonsland ({dest}) er ulikt sluttbrukerland "
                    f"({eu_country}) der ett er sanksjonert."
                ),
                entity_name=eu_name,
                country=dest,
            )
        )

    # 7. Udeklarert sluttbruker ved eksport til høyrisikoland
    if end_user is None and worst_country_risk in ("high", "elevated"):
        signals.append(
            CatchAllSignal(
                signal_type="undeclared_end_user",
                severity="yellow",
                title="Udeklarert sluttbruker",
                detail=f"Ingen sluttbruker er identifisert ved eksport til høyrisikoland ({dest}).",
                entity_name=None,
                country=dest,
            )
        )

    if not signals:
        return CatchAllCheckResult(
            flagged=False,
            status=_STATUS_CLEAR,
            severity="green",
            end_user_name=eu_name,
            end_user_country=eu_country,
            destination_country=dest,
            signals=[],
            summary=None,
        )

    has_red = any(s.severity == "red" for s in signals)
    status = _STATUS_CONTROLLED if has_red else _STATUS_REVIEW
    severity = "red" if has_red else "yellow"
    summary = _build_summary(signals, status)

    return CatchAllCheckResult(
        flagged=True,
        status=status,
        severity=severity,
        end_user_name=eu_name,
        end_user_country=eu_country,
        destination_country=dest,
        signals=signals,
        summary=summary,
    )


def _build_summary(signals: list[CatchAllSignal], status: str) -> str:
    titles = []
    seen: set[str] = set()
    for s in signals:
        if s.signal_type not in seen:
            titles.append(s.title)
            seen.add(s.signal_type)
    prefix = "🔴 Catch-all: lisens kan kreves" if status == _STATUS_CONTROLLED else (
        "🟡 Catch-all: krever egenvurdering"
    )
    return f"{prefix} — {'; '.join(titles)}"[:512]


# ── Worklist-spørringer ───────────────────────────────────────────────────────

_SCREENED_STATUSES = (
    InvoiceStatus.SCREENED,
    InvoiceStatus.REVIEWED,
    InvoiceStatus.APPROVED,
    InvoiceStatus.BLOCKED,
)


async def list_catch_all_invoices(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    flagged_only: bool = True,
    signal_filter: str | None = None,
) -> tuple[list[CatchAllCheckResult], list[Invoice], int, int]:
    """Hent fakturaer med catch-all-vurdering for arbeidslista.

    Returnerer (results, invoices, total_flagged, total_scanned).
    """
    total_scanned: int = (
        await session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.catch_all_status.is_not(None))
        )
    ).scalar_one()
    total_flagged: int = (
        await session.execute(
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.catch_all_status.in_([_STATUS_REVIEW, _STATUS_CONTROLLED]))
        )
    ).scalar_one()

    stmt = (
        select(Invoice)
        .options(selectinload(Invoice.entities), selectinload(Invoice.lines))
        .order_by(Invoice.created_at.desc())
    )
    if flagged_only:
        stmt = stmt.where(Invoice.catch_all_status.in_([_STATUS_REVIEW, _STATUS_CONTROLLED]))
    else:
        stmt = stmt.where(Invoice.catch_all_status.is_not(None))
    stmt = stmt.limit(limit).offset(offset)

    invoices = list((await session.execute(stmt)).scalars().all())
    results: list[CatchAllCheckResult] = []
    kept: list[Invoice] = []
    for inv in invoices:
        res = evaluate_invoice_catch_all(inv)
        if signal_filter and not any(s.signal_type == signal_filter for s in res.signals):
            continue
        results.append(res)
        kept.append(inv)
    return results, kept, total_flagged, total_scanned


async def backfill_catch_all(
    session: AsyncSession,
    *,
    rescore: bool = True,
    batch_size: int = 200,
) -> dict[str, int]:
    """Beregn catch-all-status for alle allerede screenede fakturaer.

    Mirrorer backfill i export_control_service. Eskalerer compliance_score kun
    for fakturaer uten manuell review-beslutning.
    """
    processed = flagged = rescored = 0
    offset = 0
    while True:
        rows = list(
            (
                await session.execute(
                    select(Invoice)
                    .options(selectinload(Invoice.entities), selectinload(Invoice.lines))
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
            res = evaluate_invoice_catch_all(inv)
            inv.catch_all_status = res.status
            inv.catch_all_summary = res.summary
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
