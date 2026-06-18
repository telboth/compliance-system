"""
Land-embargo-sjekk for sanksjonsscreening.

Denne modulen eksponerer tre synkrone funksjoner som brukes overalt i systemet:
  check_country(iso2)            -> EmbargoEntry | None
  is_comprehensive_embargo(iso2) -> bool
  is_sanctioned(iso2)            -> bool

Ved oppstart lastes embargo-data fra databasen (embargo_countries-tabellen)
inn i en in-memory cache via load_cache_from_db(). Frem til det skjer (og som
fallback dersom DB er tom) brukes den hardkodede SEED_LIST nedenfor.

Bakgrunn: Land som KP (Nord-Korea), IR (Iran) og SY (Syria) er under
total embargo -- det er forbudt a eksportere dit uavhengig av om
den konkrete kjoperen er navngitt pa en SDN-liste. Entity-name matching
alene fanger ikke dette.

Kilder (seed per juni 2026):
  UN  -- FN Sikkerhetsrads resolusjoner (kap. VII)
  EU  -- EUs restriktive tiltak (forordninger 2580/2001, 833/2014 m.fl.)
  NO  -- Norsk eksportkontrollregelverk og sanksjonsforskrifter
  US  -- OFAC Country-Based Sanctions Programs

Viktig: Beslutningsstotte, ikke juridisk raadgivning.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbargoEntry:
    """Ett sanksjonert land med metadata."""

    iso2: str
    name: str
    sources: tuple[str, ...]
    scope: str   # "comprehensive" | "sectoral"
    note: str


# ── Seed-liste (fallback / initial DB-seed) ───────────────────────────────────

SEED_LIST: tuple[EmbargoEntry, ...] = (
    # ── Totale embargoer ─────────────────────────────────────────────────────
    EmbargoEntry(
        iso2="KP", name="Nord-Korea (DPRK)",
        sources=("UN", "EU", "NO", "US"), scope="comprehensive",
        note="FN SR res. 1718 (2006) og 2397 (2017). "
             "Totalforbud mot eksport av nesten alle varer, inkl. dual-use.",
    ),
    EmbargoEntry(
        iso2="IR", name="Iran",
        sources=("UN", "EU", "NO", "US"), scope="comprehensive",
        note="OFAC Iran Sanctions + EU-forordning 267/2012. "
             "Totalforbud inkl. dual-use og militaert materiell.",
    ),
    EmbargoEntry(
        iso2="SY", name="Syria",
        sources=("EU", "NO", "US"), scope="comprehensive",
        note="EU-forordning 36/2012. Totalforbud mot eksport av "
             "varer/teknologi som kan brukes til intern undertrykking.",
    ),
    EmbargoEntry(
        iso2="CU", name="Cuba",
        sources=("US",), scope="comprehensive",
        note="OFAC Cuba Assets Control Regulations (CACR). "
             "US-totalembargo. Norske eksportorer maa ta hensyn "
             "ved re-eksport av US-kontrollert innhold (EAR-regler).",
    ),
    # ── Brede sektorielle sanksjoner ─────────────────────────────────────────
    EmbargoEntry(
        iso2="RU", name="Russland",
        sources=("EU", "NO"), scope="sectoral",
        note="EU-forordning 833/2014 (endret 2022-2024). "
             "Omfattende eksportforbud: forsvar, dual-use, avansert teknologi, "
             "luksusvarer, energisektoren. Krever grundig ECCN/HS-vurdering.",
    ),
    EmbargoEntry(
        iso2="BY", name="Hviterussland",
        sources=("EU", "NO"), scope="sectoral",
        note="EU-forordning 765/2006 (endret 2022). "
             "Forbud mot dual-use og forsvarsmateriell. "
             "Hoyrisikoland for transitt til Russland.",
    ),
    # ── Andre FN/EU/US-sanksjoner ─────────────────────────────────────────────
    EmbargoEntry(
        iso2="MM", name="Myanmar",
        sources=("EU", "US"), scope="sectoral",
        note="EU-forordning 401/2013. Forbud mot militaert og dual-use "
             "materiell etter militaerkuppet i 2021.",
    ),
    EmbargoEntry(
        iso2="SD", name="Sudan",
        sources=("UN", "US"), scope="sectoral",
        note="OFAC Sudan Sanctions + FN-vapenembargo. "
             "Forbudt: vapen og militaert utstyr til Darfur.",
    ),
    EmbargoEntry(
        iso2="SS", name="Sor-Sudan",
        sources=("UN",), scope="sectoral",
        note="FN SR res. 2428 (2018). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="LY", name="Libya",
        sources=("UN", "EU"), scope="sectoral",
        note="FN SR res. 1970 (2011). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="SO", name="Somalia",
        sources=("UN",), scope="sectoral",
        note="FN SR res. 733 (1992) og etterfolgere. Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="YE", name="Jemen",
        sources=("UN",), scope="sectoral",
        note="FN SR res. 2140 (2014). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="CF", name="Den sentralafrikanske republikk",
        sources=("UN",), scope="sectoral",
        note="FN SR res. 2127 (2013). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="ML", name="Mali",
        sources=("UN", "EU"), scope="sectoral",
        note="FN SR res. 2374 (2017). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="CD", name="Den demokratiske republikken Kongo",
        sources=("UN", "EU"), scope="sectoral",
        note="FN SR res. 1493 (2003). Vapenembargo mot ikke-statlige grupper.",
    ),
    EmbargoEntry(
        iso2="IQ", name="Irak",
        sources=("UN",), scope="sectoral",
        note="FN SR res. 1483 (2003). Restriksjoner pa vapen til ikke-statlige.",
    ),
    EmbargoEntry(
        iso2="LB", name="Libanon",
        sources=("UN",), scope="sectoral",
        note="FN SR res. 1701 (2006). Restriksjoner mot bevapning av "
             "ikke-statlige grupper.",
    ),
    EmbargoEntry(
        iso2="VE", name="Venezuela",
        sources=("EU", "US"), scope="sectoral",
        note="EU-forordning 2017/2063. Forbud mot vapen og "
             "internt undertrykkingsutstyr. OFAC-sanksjoner pa statsoljeselskap.",
    ),
    EmbargoEntry(
        iso2="ZW", name="Zimbabwe",
        sources=("EU",), scope="sectoral",
        note="EU-forordning 2011/101. Forbud mot vapen og "
             "internt undertrykkingsutstyr.",
    ),
    EmbargoEntry(
        iso2="HT", name="Haiti",
        sources=("UN",), scope="sectoral",
        note="FN SR res. 2653 (2022). Vapenembargo.",
    ),
)

# Beholdt for bakoverkompatibilitet — ekstern kode som importerer EMBARGO_LIST
# vil fortsatt fungere (den faar seed-lista).
EMBARGO_LIST = SEED_LIST

# ── In-memory cache (None = ikke lastet fra DB enda, fall tilbake til seed) ───

_DB_CACHE: dict[str, EmbargoEntry] | None = None

_SEED_INDEX: dict[str, EmbargoEntry] = {e.iso2.upper(): e for e in SEED_LIST}


def _get_index() -> dict[str, EmbargoEntry]:
    """Returner DB-cache hvis lastet, ellers seed-lista."""
    return _DB_CACHE if _DB_CACHE is not None else _SEED_INDEX


# ── Async DB-lasting (kalles ved oppstart og etter import) ────────────────────


async def load_cache_from_db(session: object) -> int:
    """Last embargo-data fra DB og erstatt in-memory cachen.

    Returnerer antall aktive land i den nye cachen.
    Kall denne ved FastAPI-oppstart og etter vellykket embargo-import.
    ``session`` er en AsyncSession — type er object for aa unngaa
    import-sirkel (embargo importeres tidlig i oppstarten).
    """
    from sqlalchemy import select as _select
    from app.models.embargo_country import EmbargoCountry

    rows = list(
        (
            await session.execute(  # type: ignore[union-attr]
                _select(EmbargoCountry).where(EmbargoCountry.is_active.is_(True))
            )
        )
        .scalars()
        .all()
    )

    if not rows:
        return 0

    global _DB_CACHE
    new_cache: dict[str, EmbargoEntry] = {}
    for row in rows:
        sources = tuple(s.strip() for s in (row.sources or "").split(",") if s.strip())
        new_cache[row.iso2.upper()] = EmbargoEntry(
            iso2=row.iso2.upper(),
            name=row.name,
            sources=sources,
            scope=row.scope,
            note=row.note or "",
        )
    _DB_CACHE = new_cache
    return len(_DB_CACHE)


async def seed_db_from_static(session: object) -> int:
    """Skriv seed-lista til DB hvis tabellen er tom. Returnerer antall nye rader."""
    from sqlalchemy import select as _select, func as _func
    from app.models.embargo_country import EmbargoCountry

    count: int = (
        await session.execute(  # type: ignore[union-attr]
            _select(_func.count()).select_from(EmbargoCountry)
        )
    ).scalar_one()

    if count > 0:
        return 0

    for entry in SEED_LIST:
        session.add(  # type: ignore[union-attr]
            EmbargoCountry(
                iso2=entry.iso2.upper(),
                name=entry.name,
                sources=", ".join(entry.sources),
                scope=entry.scope,
                note=entry.note,
                is_active=True,
                source_version="seed",
            )
        )
    await session.commit()  # type: ignore[union-attr]
    return len(SEED_LIST)


# ── Offentlig API (synkron, uendret signaturer) ───────────────────────────────


def check_country(iso2: str | None) -> EmbargoEntry | None:
    """Returner EmbargoEntry om landet er paa lista, ellers None."""
    if not iso2:
        return None
    return _get_index().get(iso2.upper().strip())


def is_comprehensive_embargo(iso2: str | None) -> bool:
    """True om landet er under total embargo (alle eksporter forbudt)."""
    entry = check_country(iso2)
    return entry is not None and entry.scope == "comprehensive"


def is_sanctioned(iso2: str | None) -> bool:
    """True om landet er paa sanksjonslisten (comprehensive eller sectoral)."""
    if not iso2:
        return False
    return iso2.upper().strip() in _get_index()


# Beholdt for kode som bruker disse direkte (les: ikke oppdateres etter DB-load)
COMPREHENSIVE_EMBARGO_COUNTRIES: frozenset[str] = frozenset(
    e.iso2.upper() for e in SEED_LIST if e.scope == "comprehensive"
)
ALL_SANCTIONED_COUNTRIES: frozenset[str] = frozenset(
    e.iso2.upper() for e in SEED_LIST
)
