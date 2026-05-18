"""
Land-embargo-sjekk for sanksjonsscreening.

Denne modulen implementerer en regel-basert forste sjekk som kjoeres
FoR entity-name matching mot yente. Dersom destinasjonslandet eller
et av partenes land er under total embargo, settes compliance_score
umiddelbart til RED uten a vente pa fuzzy-matching.

Bakgrunn: Land som KP (Nord-Korea), IR (Iran) og SY (Syria) er under
total embargo -- det er forbudt a eksportere dit uavhengig av om
den konkrete kjoperen er navngitt pa en SDN-liste. Entity-name matching
alene fanger ikke dette.

Kilder (per mai 2026):
  UN  -- FN Sikkerhetsrads resolusjoner (kap. VII)
  EU  -- EUs restriktive tiltak (forordninger 2580/2001, 833/2014 m.fl.)
  NO  -- Norsk eksportkontrollregelverk og sanksjonsforskrifter
  US  -- OFAC Country-Based Sanctions Programs

Viktig: Denne listen er ikke juridisk raadgivning. For full etterlevelse
ta kontakt med Utenriksdepartementet og/eller juridisk ekspert.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbargoEntry:
    """Ett sanksjonert land med metadata."""

    iso2: str
    name: str
    # Hvilke regelverk som legger embargo
    sources: tuple[str, ...]
    # Omfang: "comprehensive" = totalforbud, "sectoral" = sektorbasert
    scope: str
    # Kort begrunnelse / notat for saksbehandler
    note: str


# ── Embargo-liste ─────────────────────────────────────────────────────────────
#
# "comprehensive" = generelt eksport- og importforbud.
# "sectoral"     = forbud mot spesifikke sektorer (forsvar, energi, finans osv.)
#                  Beholder for a flagge hoyrisikoland selv om de ikke er
#                  totalembargert.

EMBARGO_LIST: tuple[EmbargoEntry, ...] = (
    # ── Totale embargoer (alle eksporter krever lisens / er forbudt) ─────────
    EmbargoEntry(
        iso2="KP", name="Nord-Korea (DPRK)",
        sources=("UN", "EU", "NO", "US"),
        scope="comprehensive",
        note="FN SR res. 1718 (2006) og 2397 (2017). "
             "Totalforbud mot eksport av nesten alle varer, inkl. dual-use.",
    ),
    EmbargoEntry(
        iso2="IR", name="Iran",
        sources=("UN", "EU", "NO", "US"),
        scope="comprehensive",
        note="OFAC Iran Sanctions + EU-forordning 267/2012. "
             "Totalforbud inkl. dual-use og militaert materiell.",
    ),
    EmbargoEntry(
        iso2="SY", name="Syria",
        sources=("EU", "NO", "US"),
        scope="comprehensive",
        note="EU-forordning 36/2012. Totalforbud mot eksport av "
             "varer/teknologi som kan brukes til intern undertrykking.",
    ),
    EmbargoEntry(
        iso2="CU", name="Cuba",
        sources=("US",),
        scope="comprehensive",
        note="OFAC Cuba Assets Control Regulations (CACR). "
             "US-totalembargo. Norske eksportorer maa ta hensyn "
             "ved re-eksport av US-kontrollert innhold (EAR-regler).",
    ),

    # ── Russland og Hviterussland (brede sektorielle sanksjoner) ─────────────
    EmbargoEntry(
        iso2="RU", name="Russland",
        sources=("EU", "NO"),
        scope="sectoral",
        note="EU-forordning 833/2014 (endret 2022-2024). "
             "Omfattende eksportforbud: forsvar, dual-use, avansert teknologi, "
             "luksusvarer, energisektoren. Krever grundig ECCN/HS-vurdering.",
    ),
    EmbargoEntry(
        iso2="BY", name="Hviterussland",
        sources=("EU", "NO"),
        scope="sectoral",
        note="EU-forordning 765/2006 (endret 2022). "
             "Forbud mot dual-use og forsvarsmateriell. "
             "Hoyrisikoland for transitt til Russland.",
    ),

    # ── Andre land under FN/EU/US-sanksjoner ─────────────────────────────────
    EmbargoEntry(
        iso2="MM", name="Myanmar",
        sources=("EU", "US"),
        scope="sectoral",
        note="EU-forordning 401/2013. Forbud mot militaert og dual-use "
             "materiell etter militaerkuppet i 2021.",
    ),
    EmbargoEntry(
        iso2="SD", name="Sudan",
        sources=("UN", "US"),
        scope="sectoral",
        note="OFAC Sudan Sanctions + FN-vapenembargo. "
             "Forbudt: vapen og militaert utstyr til Darfur.",
    ),
    EmbargoEntry(
        iso2="SS", name="Sor-Sudan",
        sources=("UN",),
        scope="sectoral",
        note="FN SR res. 2428 (2018). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="LY", name="Libya",
        sources=("UN", "EU"),
        scope="sectoral",
        note="FN SR res. 1970 (2011). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="SO", name="Somalia",
        sources=("UN",),
        scope="sectoral",
        note="FN SR res. 733 (1992) og etterfolgere. Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="YE", name="Jemen",
        sources=("UN",),
        scope="sectoral",
        note="FN SR res. 2140 (2014). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="CF", name="Den sentralafrikanske republikk",
        sources=("UN",),
        scope="sectoral",
        note="FN SR res. 2127 (2013). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="ML", name="Mali",
        sources=("UN", "EU"),
        scope="sectoral",
        note="FN SR res. 2374 (2017). Vapenembargo.",
    ),
    EmbargoEntry(
        iso2="CD", name="Den demokratiske republikken Kongo",
        sources=("UN", "EU"),
        scope="sectoral",
        note="FN SR res. 1493 (2003). Vapenembargo mot ikke-statlige grupper.",
    ),
    EmbargoEntry(
        iso2="IQ", name="Irak",
        sources=("UN",),
        scope="sectoral",
        note="FN SR res. 1483 (2003). Restriksjoner pa vapen til ikke-statlige.",
    ),
    EmbargoEntry(
        iso2="LB", name="Libanon",
        sources=("UN",),
        scope="sectoral",
        note="FN SR res. 1701 (2006). Restriksjoner mot bevapning av "
             "ikke-statlige grupper.",
    ),
    EmbargoEntry(
        iso2="VE", name="Venezuela",
        sources=("EU", "US"),
        scope="sectoral",
        note="EU-forordning 2017/2063. Forbud mot vapen og "
             "internt undertrykkingsutstyr. OFAC-sanksjoner pa statsoljeselskap.",
    ),
    EmbargoEntry(
        iso2="ZW", name="Zimbabwe",
        sources=("EU",),
        scope="sectoral",
        note="EU-forordning 2011/101. Forbud mot vapen og "
             "internt undertrykkingsutstyr.",
    ),
    EmbargoEntry(
        iso2="HT", name="Haiti",
        sources=("UN",),
        scope="sectoral",
        note="FN SR res. 2653 (2022). Vapenembargo.",
    ),
)

# ── Oppslags-dict for rask O(1) sjekk ────────────────────────────────────────

_EMBARGO_BY_ISO2: dict[str, EmbargoEntry] = {
    e.iso2.upper(): e for e in EMBARGO_LIST
}

# ISO2-koder under total embargo (umiddelbart RED uavhengig av ECCN/vare)
COMPREHENSIVE_EMBARGO_COUNTRIES: frozenset[str] = frozenset(
    e.iso2.upper() for e in EMBARGO_LIST if e.scope == "comprehensive"
)

# Alle sanksjonerte land (comprehensive + sectoral) — gir YELLOW om ikke RED
ALL_SANCTIONED_COUNTRIES: frozenset[str] = frozenset(
    e.iso2.upper() for e in EMBARGO_LIST
)


def check_country(iso2: str | None) -> EmbargoEntry | None:
    """Returner EmbargoEntry om landet er pa lista, ellers None.

    Args:
        iso2: ISO 3166-1 alfa-2 landkode (case-insensitive).

    Returns:
        EmbargoEntry om landet er sanksjonert, None ellers.
    """
    if not iso2:
        return None
    return _EMBARGO_BY_ISO2.get(iso2.upper().strip())


def is_comprehensive_embargo(iso2: str | None) -> bool:
    """True om landet er under total embargo (alle eksporter forbudt)."""
    if not iso2:
        return False
    return iso2.upper().strip() in COMPREHENSIVE_EMBARGO_COUNTRIES


def is_sanctioned(iso2: str | None) -> bool:
    """True om landet er pa sanksjonslisten (comprehensive eller sectoral)."""
    if not iso2:
        return False
    return iso2.upper().strip() in ALL_SANCTIONED_COUNTRIES
