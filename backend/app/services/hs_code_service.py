"""HS-kode klassifiseringstjeneste.

Statisk oppslagstabell for risikovurdering av HS-koder (Harmonized System).
Ingen ekstern API eller DB — tabellen oppdateres manuelt ved behov.

HS-struktur:
  - Kapittel:    2 siffer  (f.eks. 93 = Våpen)
  - Heading:     4 siffer  (f.eks. 8542 = Halvledere)
  - Sub-heading: 6+ siffer (spesifikk vare)

Risikonivå: "high" | "medium" | "low" | None
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HSClassification:
    code: str
    chapter: str
    chapter_description: str
    heading: str | None
    heading_description: str | None
    risk_level: str | None          # "high" | "medium" | None
    risk_reason: str | None
    is_controlled: bool             # krever eksportlisens / ekstra aktsomhet
    dual_use_flag: bool


# ── Kapittel-tabell ────────────────────────────────────────────────────────────
# Kilde: WCO Harmonized System 2022, EU Dual-Use-forordning 2021/821,
#        norsk eksportkontrollforskrift Liste I og II.

_CHAPTER_RISK: dict[str, tuple[str, str | None, str | None, bool]] = {
    # (beskrivelse, risk_level, risk_reason, is_controlled)
    "22": ("Drikkevarer, alkohol og eddik", "medium", "Eksportrestriksjoner til visse land", False),
    "28": ("Uorganiske kjemikalier", "medium", "Dual-use potensiale — kjemiske forløpere", True),
    "29": ("Organiske kjemikalier", "medium", "Dual-use potensiale — kjemiske forløpere", True),
    "30": ("Farmasøytiske produkter", "medium", "Eksportkontroll mot enkelte destinasjoner", False),
    "36": ("Eksplosiver og pyrotekniske produkter", "high", "Eksplosiver — streng eksportkontroll", True),
    "37": ("Fotografiske produkter", None, None, False),
    "38": ("Diverse kjemiske produkter", "medium", "Dual-use kjemikalier mulig", True),
    "39": ("Plast og plastprodukter", None, None, False),
    "40": ("Gummi og gummiprodukter", None, None, False),
    "72": ("Jern og stål", None, None, False),
    "73": ("Varer av jern og stål", None, None, False),
    "74": ("Kobber og kobberprodukter", None, None, False),
    "76": ("Aluminium og aluminiumsprodukter", None, None, False),
    "82": ("Verktøy og skjæreredskaper av uedle metaller", None, None, False),
    "83": ("Diverse varer av uedle metaller", None, None, False),
    "84": ("Maskiner og mekaniske apparater", "medium", "Dual-use maskiner og nykleær teknologi mulig — sjekk ECCN", True),
    "85": ("Elektriske maskiner og apparater", "medium", "Elektronikk med dual-use potensiale — sjekk ECCN", True),
    "86": ("Jernbanemateriell", None, None, False),
    "87": ("Kjøretøy unntatt jernbanevogner", "medium", "Militære kjøretøy mulig (8710)", True),
    "88": ("Luftfartøy og romfartøy", "high", "Flymateriell — streng eksportkontroll (EAR/ITAR)", True),
    "89": ("Skip og fartøy", "medium", "Militære fartøy mulig — krev sluttbrukererklæring", True),
    "90": ("Optiske og presisjonsinstrumenter", "medium", "Dual-use — presisjonsmåling og militær optikk", True),
    "91": ("Ur og deler til ur", None, None, False),
    "92": ("Musikkinstrumenter", None, None, False),
    "93": ("Våpen, ammunisjon og deler", "high", "Militært materiell — strengeste eksportkontroll", True),
    "94": ("Møbler og belysningsutstyr", None, None, False),
}

# ── Heading-tabell (4-sifret) — overstyrer kapittelnivå ──────────────────────
_HEADING_RISK: dict[str, tuple[str, str | None, str | None, bool]] = {
    # Kapittel 84 — viktige dual-use headings
    "8401": ("Nukleære reaktorer", "high", "Nukleær teknologi — streng eksportkontroll", True),
    "8471": ("Datamaskiner og databehandlingsutstyr", "medium", "IT-utstyr med dual-use potensiale", True),
    "8479": ("Maskiner og apparater med spesifikk funksjon", "medium", "Dual-use potensiale", True),
    "8483": ("Transmisjonsutstyr", "medium", "Presisjonsmaskiner — sjekk ECCN", False),
    "8486": ("Halvlederfabrikasjonsmaskiner", "high", "Avansert produksjonsutstyr — eksportlisens kan kreves", True),
    # Kapittel 85 — viktige dual-use headings
    "8517": ("Telekommunikasjonsutstyr", "medium", "Telekomutstyr med dual-use potensiale — sjekk ECCN", True),
    "8523": ("Lagringsmedia — programvare", "medium", "Kryptografi og programvare kan kreve lisens", True),
    "8524": ("Halvledere og integrerte kretser", "medium", "Halvledere — eksportrestriksjoner mot Kina", True),
    "8526": ("Radar og radionavigasjon", "high", "Navigasjonsutstyr — militær bruk mulig", True),
    "8542": ("Elektroniske integrerte kretser", "high", "Avanserte halvledere — US/EU eksportkontroll", True),
    "8543": ("Elektriske maskiner og apparater", "medium", "Spesialmaskiner — dual-use mulig", True),
    # Kapittel 87 — militære kjøretøy
    "8710": ("Stridsvogner og pansrede kjøretøy", "high", "Militært materiell — totalforbud mange destinasjoner", True),
    # Kapittel 90 — presisjonsinstrumenter
    "9005": ("Kikkere og kikkerter", "medium", "Optisk utstyr — militær bruk mulig", True),
    "9013": ("Lasere og optiske instrumenter", "high", "Laser — militær/dual-use — sjekk ECCN", True),
    "9014": ("Retningsfinnende og navigasjonsinstrumenter", "high", "Militær navigasjon — streng kontroll", True),
    "9015": ("Geodetisk og hydrografisk utstyr", "medium", "Presisjonsmåling — militær bruk mulig", True),
    "9306": ("Bomber, granater og missiler", "high", "Krigsmateriell — totalforbud", True),
}


def classify(hs_code: str) -> HSClassification | None:
    """Klassifiser en HS-kode og returner risikovurdering.

    Args:
        hs_code: HS-kode som streng (alle lengder — 2, 4, 6, 8, 10 siffer).
                 Kan inneholde punktum og mellomrom (renses automatisk).

    Returns:
        HSClassification eller None hvis koden er tom/ugyldig.
    """
    if not hs_code:
        return None

    # Rens koden — fjern punktum, mellomrom, bindestreker
    clean = hs_code.replace(".", "").replace(" ", "").replace("-", "").strip()
    if not clean.isdigit() or len(clean) < 2:
        return None

    chapter = clean[:2]
    heading = clean[:4] if len(clean) >= 4 else None

    # Slå opp — heading overstyrer kapittel
    if heading and heading in _HEADING_RISK:
        hdesc, risk_level, risk_reason, is_controlled = _HEADING_RISK[heading]
        chap_info = _CHAPTER_RISK.get(chapter, ("Ukjent kapittel", None, None, False))
        return HSClassification(
            code=clean,
            chapter=chapter,
            chapter_description=chap_info[0],
            heading=heading,
            heading_description=hdesc,
            risk_level=risk_level,
            risk_reason=risk_reason,
            is_controlled=is_controlled,
            dual_use_flag=risk_level in ("medium", "high") and is_controlled,
        )

    if chapter in _CHAPTER_RISK:
        cdesc, risk_level, risk_reason, is_controlled = _CHAPTER_RISK[chapter]
        return HSClassification(
            code=clean,
            chapter=chapter,
            chapter_description=cdesc,
            heading=heading,
            heading_description=None,
            risk_level=risk_level,
            risk_reason=risk_reason,
            is_controlled=is_controlled,
            dual_use_flag=risk_level in ("medium", "high") and is_controlled,
        )

    # Ukjent kapittel — returner lav-risiko klassifisering
    return HSClassification(
        code=clean,
        chapter=chapter,
        chapter_description="Ikke klassifisert",
        heading=heading,
        heading_description=None,
        risk_level=None,
        risk_reason=None,
        is_controlled=False,
        dual_use_flag=False,
    )
