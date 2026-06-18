"""Statisk referanse for DEKSAs eksportkontroll-varelister (Vareliste I og II).

Denne modulen er den *alltid tilgjengelige* ryggraden for listematching: den
beskriver kategoristrukturen i de norske varelistene og et kuratert
nøkkelordleksikon per kategori. Den er bevisst holdt på *kategorinivå* slik at
den er trygg å vedlikeholde manuelt og aldri blir utdatert på struktur.

Den fullstendige, maskinlesbare punktlista (f.eks. 6A001.a.2.a.6) lastes inn
i databasen via ``scripts/import_dual_use_list.py`` fra EU-kommisjonens
offisielle Annex I-Excel. Vareliste II er en norsk oversettelse av EUs
dual-use-liste (forordning 2021/821), og Vareliste I følger Wassenaar
Munitions List / EUs felles liste over militært materiell.

Kilder:
  - https://deksa.no/eksportkontroll/trenger-du-lisens/varelister/
  - EU dual-use Annex I (forordning 2021/821 m. endringer)
  - Wassenaar Arrangement Munitions List

VIKTIG: Dette er beslutningsstøtte, ikke en juridisk avgjørelse. Endelig
kontrollstatus avgjøres av eksportørens tekniske egenvurdering mot lista og
DEKSAs vurdering. Tekniske parametre (sensitivitet, ytelse, materialkvalitet)
kan ikke avgjøres fra en faktura alene.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ControlCategory:
    """Én kategori i en vareliste, med kuraterte søkeord for tekstmatch."""

    list_code: str  # "I" (militært) | "II" (dual-use)
    category: str  # "ML10" eller "6" / "6A"
    title_no: str
    title_en: str
    keywords: tuple[str, ...] = field(default_factory=tuple)
    regime: str | None = None  # Wassenaar | NSG | MTCR | AG | CWC


# ── Vareliste I — Forsvarsmateriell (ML1-ML22) ────────────────────────────────
# Basert på EUs felles liste over militært materiell / Wassenaar Munitions List.

LIST_I_CATEGORIES: tuple[ControlCategory, ...] = (
    ControlCategory(
        "I",
        "ML1",
        "Glattborede våpen under 20 mm, andre våpen ≤12,7 mm",
        "Smooth-bore weapons <20mm, other arms ≤12.7mm",
        (
            "rifle",
            "carbine",
            "pistol",
            "revolver",
            "machine gun",
            "submachine gun",
            "assault rifle",
            "firearm",
            "shotgun",
            "musket",
            "gevær",
            "automatvåpen",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML2",
        "Glattborede våpen ≥20 mm, andre våpen >12,7 mm, kanoner",
        "Weapons ≥20mm, other weapons/armament >12.7mm, mortars",
        (
            "cannon",
            "howitzer",
            "mortar",
            "grenade launcher",
            "artillery",
            "autocannon",
            "kanon",
            "bombekaster",
            "granatkaster",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML3",
        "Ammunisjon og tennmekanismer",
        "Ammunition and fuze setting devices",
        (
            "ammunition",
            "cartridge",
            "fuze",
            "fuse",
            "projectile",
            "shell",
            "round",
            "tracer",
            "ammunisjon",
            "patron",
            "prosjektil",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML4",
        "Bomber, torpedoer, raketter, missiler",
        "Bombs, torpedoes, rockets, missiles, related equipment",
        (
            "bomb",
            "torpedo",
            "missile",
            "rocket",
            "warhead",
            "mine",
            "depth charge",
            "ied",
            "stridshode",
            "missil",
            "rakett",
        ),
        "MTCR",
    ),
    ControlCategory(
        "I",
        "ML5",
        "Ildledning og tilhørende varslingsutstyr",
        "Fire control, surveillance and warning equipment",
        ("fire control", "weapon sight", "laser rangefinder", "target acquisition", "ildledning", "siktemiddel"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML6",
        "Landkjøretøy og komponenter",
        "Ground vehicles and components",
        (
            "armoured vehicle",
            "armored vehicle",
            "tank",
            "military vehicle",
            "apc",
            "infantry fighting vehicle",
            "pansret kjøretøy",
            "stridsvogn",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML7",
        "Kjemiske/biologiske stridsmidler og opprørskontroll",
        "Chemical/biological agents, riot control agents",
        (
            "nerve agent", "nervegass",
            "tear gas", "tåregass",
            "cs gas", "cn gas",
            "riot control", "opprørskontroll",
            "toxin", "toksin",
            "chemical agent", "kjemisk stridsmiddel",
            "biological agent", "biologisk stridsmiddel",
            "sarin", "tabun", "soman", "VX",
            "mustard gas", "sennepsgass",
            "lewisite", "lewisitt",
            "phosgene", "fosgen",
            "blister agent", "vesikant",
            "incapacitating agent", "inkapasiteringsmiddel",
            "CWC Schedule", "OPCW",
            "anthrax", "antraks",
            "pepper spray", "pepperspray",
            "capsaicin",
        ),
        "CWC",
    ),
    ControlCategory(
        "I",
        "ML8",
        "Energetiske materialer og relaterte stoffer",
        "Energetic materials and related substances (explosives, propellants)",
        ("explosive", "rdx", "hmx", "tnt", "petn", "propellant", "nitrocellulose", "eksplosiv", "krutt", "drivladning"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML9",
        "Krigsfartøyer og marint utstyr",
        "Vessels of war and special naval equipment",
        ("warship", "submarine", "naval vessel", "torpedo tube", "minesweeper", "krigsfartøy", "ubåt", "marinefartøy"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML10",
        "Luftfartøyer, UAV-er og flymotorer",
        "Aircraft, UAVs, aero engines and equipment",
        (
            "military aircraft",
            "fighter jet",
            "uav",
            "unmanned aerial",
            "drone",
            "aero engine",
            "kampfly",
            "militært luftfartøy",
        ),
        "MTCR",
    ),
    ControlCategory(
        "I",
        "ML11",
        "Elektronisk utstyr (militært)",
        "Electronic equipment, spacecraft and components (military)",
        (
            "electronic warfare",
            "jamming",
            "ecm",
            "countermeasure",
            "military radar",
            "elektronisk krigføring",
            "jamming",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML12",
        "Høyhastighets kinetiske energivåpen",
        "High velocity kinetic energy weapon systems",
        ("railgun", "kinetic energy weapon", "kinetisk energivåpen"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML13",
        "Pansret eller beskyttende utstyr",
        "Armoured or protective equipment",
        ("body armour", "body armor", "ballistic protection", "armour plate", "helmet", "skuddsikker", "kroppspanser"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML14",
        "Spesialisert treningsutstyr",
        "Specialised equipment for military training",
        ("military simulator", "training simulator", "militær simulator"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML15",
        "Bildedannende og mottiltaksutstyr",
        "Imaging or countermeasure equipment (military)",
        ("night vision", "thermal imaging", "image intensifier", "nattsyn", "termisk avbildning"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML16",
        "Smigods, støpegods og halvfabrikata",
        "Forgings, castings and unfinished products for ML items",
        ("forging", "casting", "smigods", "støpegods"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML17",
        "Diverse utstyr, materialer og biblioteker",
        "Miscellaneous equipment, materials and libraries",
        ("military robot", "military diving", "armoured shelter"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML18",
        "Produksjonsutstyr for ML-varer",
        "Production equipment for ML items",
        ("production equipment", "produksjonsutstyr militært"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML19",
        "Rettede energivåpensystemer",
        "Directed energy weapon systems",
        ("directed energy", "laser weapon", "high power microwave", "rettet energivåpen", "laservåpen"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML20",
        "Kryogenisk og superledende utstyr (militært)",
        "Cryogenic and superconductive equipment (military)",
        ("cryogenic military", "superconductive military"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML21",
        "Programvare (militær)",
        "Software for military use",
        ("military software", "fire control software", "militær programvare"),
        "Wassenaar",
    ),
    ControlCategory(
        "I",
        "ML22",
        "Teknologi (militær)",
        "Technology for the development/production/use of ML items",
        ("military technology", "technical data military", "militær teknologi"),
        "Wassenaar",
    ),
)


# ── Vareliste II — Flerbruksvarer (kategori 0-9) ──────────────────────────────
# Norsk oversettelse av EUs dual-use-liste (Annex I, forordning 2021/821).
# Hver kategori deles i grupper A-E:
#   A=systemer/utstyr, B=test-/produksjonsutstyr, C=materialer,
#   D=programvare, E=teknologi.

LIST_II_CATEGORIES: tuple[ControlCategory, ...] = (
    ControlCategory(
        "II",
        "0",
        "Kjernefysiske materialer, anlegg og utstyr",
        "Nuclear materials, facilities and equipment",
        (
            "uranium",
            "plutonium",
            "centrifuge",
            "nuclear reactor",
            "heavy water",
            "isotope separation",
            "tritium",
            "zirconium",
            "uran",
            "plutonium",
            "sentrifuge",
            "kjernereaktor",
            "tungtvann",
        ),
        "NSG",
    ),
    ControlCategory(
        "II",
        "1",
        "Spesielle materialer og tilhørende utstyr",
        "Special materials and related equipment",
        (
            # Komposittmaterialer
            "carbon fiber",
            "carbon fibre",
            "aramid",
            "composite material",
            "karbonfiber",
            "kompositt",
            # Metaller og legeringer (1C002/1C011)
            "tungsten",
            "wolfram",
            "beryllium",
            "hafnium",
            "niobium",
            "columbium",
            "rhenium",
            "zirconium",
            "zirkonium",
            "germanium",
            "hard metal",
            "hardmetall",
            "cemented carbide",
            "sintret karbid",
            "tungsten carbide",
            "wolframkarbid",
            # Kjemiske forløpere og toksiske materialer (1C350/1C450)
            "chemical precursor",
            "kjemisk forløper",
            "toxic",
            "toksisk",
            "fluorinated",
            "boron",
            "ammonium perchlorate",
            "ammoniumperklorat",
            "thiodiglycol",
            "tiodiglykol",
            "phosphorus trichloride",
            "fosfortriklorid",
            "phosgene",
            "fosgen",
            "hydrogen cyanide",
            "hydrogencyanid",
            # Eksplosiver og drivstoff (1C111/1C210)
            "explosive",
            "sprengstoff",
            "propellant",
            "drivstoff",
            "nitrocellulose",
            "RDX",
            "HMX",
            "TNT",
            "PETN",
            "HTPB",
            # Nukleære materialer (1C232–1C234)
            "tritium",
            "lithium-6",
            "litium-6",
            "nuclear material",
            "nukleært materiale",
        ),
        "AG",
    ),
    ControlCategory(
        "II",
        "2",
        "Materialbearbeiding",
        "Materials processing",
        (
            "machine tool",
            "cnc",
            "five axis",
            "isostatic press",
            "bearing",
            "robot",
            "spin forming",
            "flow forming",
            "verktøymaskin",
            "dreiebenk",
            "fresemaskin",
            "industrirobot",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "II",
        "3",
        "Elektronikk",
        "Electronics",
        (
            "integrated circuit",
            "microprocessor",
            "fpga",
            "asic",
            "adc",
            "radiation hardened",
            "microwave",
            "vacuum electronic",
            "semiconductor",
            "integrert krets",
            "mikroprosessor",
            "halvleder",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "II",
        "4",
        "Datamaskiner",
        "Computers",
        (
            "supercomputer",
            "high performance computing",
            "hpc",
            "neural computer",
            "tflops",
            "superdatamaskin",
            "tungregning",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "II",
        "5",
        "Telekommunikasjon og informasjonssikkerhet",
        "Telecommunications and information security (cryptography)",
        (
            "encryption",
            "cryptography",
            "cryptographic",
            "telecommunication",
            "signal processing",
            "jamming",
            "monitoring",
            "interception",
            "kryptering",
            "kryptografi",
            "telekommunikasjon",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "II",
        "6",
        "Sensorer og lasere",
        "Sensors and lasers",
        (
            "laser",
            "sensor",
            "radar",
            "sonar",
            "hydrophone",
            "accelerometer",
            "gyroscope",
            "infrared",
            "focal plane array",
            "night vision",
            "lidar",
            "laser",
            "sensor",
            "radar",
            "gyroskop",
            "infrarød",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "II",
        "7",
        "Navigasjon og luftelektronikk",
        "Navigation and avionics",
        (
            "inertial navigation",
            "ins",
            "imu",
            "gyroscope",
            "accelerometer",
            "gnss",
            "gps receiver",
            "flight control",
            "avionics",
            "treghetsnavigasjon",
            "flynavigasjon",
        ),
        "MTCR",
    ),
    ControlCategory(
        "II",
        "8",
        "Marine",
        "Marine",
        (
            "submersible",
            "submarine",
            "underwater vehicle",
            "rov",
            "auv",
            "diving system",
            "marine propulsion",
            "undervannsfartøy",
            "dykkersystem",
        ),
        "Wassenaar",
    ),
    ControlCategory(
        "II",
        "9",
        "Luft- og romfart samt fremdrift",
        "Aerospace and propulsion",
        (
            "gas turbine",
            "jet engine",
            "rocket engine",
            "turbojet",
            "turbofan",
            "uav",
            "spacecraft",
            "propellant",
            "ramjet",
            "gassturbin",
            "jetmotor",
            "rakettmotor",
            "romfartøy",
        ),
        "MTCR",
    ),
)

ALL_CATEGORIES: tuple[ControlCategory, ...] = LIST_I_CATEGORIES + LIST_II_CATEGORIES

# Oppslag på kategori-kode (uppercase) → ControlCategory
_BY_CATEGORY: dict[str, ControlCategory] = {c.category.upper(): c for c in ALL_CATEGORIES}


# ── Strukturell parsing av kontrollkoder (ECCN / ML) ──────────────────────────

# Militær liste: ML etterfulgt av 1-2 siffer (ML1, ML10, ML 22)
_ML_RE = re.compile(r"^\s*ML\s*(\d{1,2})\b", re.IGNORECASE)
# Dual-use / ECCN: kategori-siffer (0-9) + gruppe-bokstav (A-E) + 3 siffer
# Eksempler: 6A001, 3A001.a, 0C002, 5A002.a.1
_DUAL_USE_RE = re.compile(r"^\s*([0-9])([A-E])(\d{3})\b", re.IGNORECASE)


@dataclass(frozen=True)
class StructuralMatch:
    """Resultat av å tolke en kontrollkode strukturelt."""

    list_code: str  # "I" | "II"
    category: str  # "ML10" | "6"
    group: str | None  # "A".."E" for dual-use, None for militært
    normalized_code: str  # ryddet kode, f.eks. "6A001"
    category_ref: ControlCategory | None


def parse_control_code(code: str | None) -> StructuralMatch | None:
    """Tolk en ECCN- eller ML-kode strukturelt mot varelistestrukturen.

    Fungerer uten databaseoppslag, og dekker både norske/EU- og
    amerikanske ECCN-koder (samme alfanumeriske skjema).

    Returnerer None hvis koden ikke ser ut som en kontrollkode.
    """
    if not code:
        return None
    raw = code.strip()

    ml = _ML_RE.match(raw)
    if ml:
        n = int(ml.group(1))
        if 1 <= n <= 22:
            cat = f"ML{n}"
            return StructuralMatch(
                list_code="I",
                category=cat,
                group=None,
                normalized_code=cat,
                category_ref=_BY_CATEGORY.get(cat),
            )

    du = _DUAL_USE_RE.match(raw)
    if du:
        cat_digit = du.group(1)
        group = du.group(2).upper()
        serial = du.group(3)
        normalized = f"{cat_digit}{group}{serial}".upper()
        return StructuralMatch(
            list_code="II",
            category=cat_digit,
            group=group,
            normalized_code=normalized,
            category_ref=_BY_CATEGORY.get(cat_digit),
        )

    return None


def category_for(category_code: str) -> ControlCategory | None:
    """Slå opp en ControlCategory på kategori-kode (ML10, 6, 6A → 6)."""
    key = category_code.strip().upper()
    if key in _BY_CATEGORY:
        return _BY_CATEGORY[key]
    # Dual-use gruppe (6A) → fall tilbake til kategori (6)
    if len(key) >= 1 and key[0].isdigit():
        return _BY_CATEGORY.get(key[0])
    return None


# Forhåndsbygget nøkkelordindeks: (keyword_lower) → ControlCategory
# Sorteres slik at lengre nøkkelord matcher først (mer spesifikke).
_KEYWORD_INDEX: tuple[tuple[str, ControlCategory], ...] = tuple(
    sorted(
        ((kw.lower(), cat) for cat in ALL_CATEGORIES for kw in cat.keywords),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
)


def keyword_matches(text: str | None) -> list[tuple[str, ControlCategory]]:
    """Finn alle nøkkelord-treff i en fritekst (typisk linjebeskrivelse).

    Returnerer liste av (matchet_nøkkelord, ControlCategory). Bruker
    ordgrense-matching for å unngå delstreng-falske positiver (f.eks.
    "laser" i "phaser"). Korte generiske ord er bevisst utelatt fra
    leksikonet.
    """
    if not text:
        return []
    hay = text.lower()
    hits: list[tuple[str, ControlCategory]] = []
    seen: set[str] = set()
    for kw, cat in _KEYWORD_INDEX:
        if kw in seen:
            continue
        # Ordgrense rundt nøkkelordet
        if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", hay):
            hits.append((kw, cat))
            seen.add(kw)
    return hits
