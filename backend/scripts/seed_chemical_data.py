#!/usr/bin/env python3
"""Seed eksportkontroll-databasen med kjemikalie- og materialdata.

Legger til CAS-numre, synonymer og HS-koder for kontrollerte kjemikalier og
materialer i de viktigste kategoriene:

  Vareliste II (dual-use, EU-forordning 2021/821):
    - 1C002 / 1C011 / 1C012  Metaller og legeringer (Wassenaar/NSG)
    - 1C111 / 1C210          Eksplosiver og rakettdrivstoff (MTCR/Wassenaar)
    - 1C232–1C234            Nukleære materialer (NSG)
    - 1C350                  CWC Schedule 1/2/3 kjemiske forløpere (AG)
    - 1C450                  Toksiske kjemikalier (AG)

  Vareliste I (militært, DEKSA):
    - ML7                    Kjemiske og biologiske stridsmidler (CWC/BWC)

Kilde: OPCW Chemical Weapons Convention Schedule, EU Dual-Use Annex I
(forordning 2021/821 m. endringer), Wassenaar Arrangement, MTCR Annex.

Eksempel:
  docker compose exec api python scripts/seed_chemical_data.py [--dry-run]

Idempotent: kan kjøres flere ganger — oppdaterer eksisterende, lager ikke duplikater.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import NamedTuple

sys.path.insert(0, "/app")

SOURCE_VERSION = "deksa-chemical-seed-v1"


class _Item(NamedTuple):
    list_code: str  # "I" | "II"
    category: str  # "ML7" | "1" | "2" ...
    group: str | None  # "A"–"E" for dual-use, None for militært
    item_code: str  # fullt kontrollnummer, f.eks. "1C350.1"
    title: str  # norsk tittel
    regime: str  # Wassenaar | NSG | MTCR | AG | CWC/OPCW
    cas_numbers: str | None  # kommaseparerte CAS, f.eks. "7440-33-7, 12070-12-1"
    synonyms: str | None  # kommaseparerte synonymer (norsk + engelsk)
    hs_codes: str | None  # kommaseparerte tolltarifnumre


# ─────────────────────────────────────────────────────────────────────────────
# Kildedata
# ─────────────────────────────────────────────────────────────────────────────

_ITEMS: list[_Item] = [
    # ══ Metaller og legeringer (1C002) — Wassenaar ═══════════════════════════
    _Item(
        "II",
        "1",
        "C",
        "1C002.b.3",
        "Tungsten-/wolframlegeringer og karbider",
        "Wassenaar",
        "7440-33-7, 12070-12-1, 12012-35-0",
        (
            "tungsten, wolfram, wolframkarbid, tungsten carbide, tungsten carbide powder, "
            "cemented carbide, sintret karbid, hard metal, hardmetall, WC, WC-Co, "
            "tungsten powder, wolframpulver, tungsten alloy, wolframlegering"
        ),
        "8101.10, 8101.94, 8101.99, 8113.00",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C002.b.5",
        "Hafniummetall, legeringer og forbindelser",
        "Wassenaar",
        "7440-58-6, 12055-23-1, 13966-91-7, 14456-34-9",
        (
            "hafnium, hafniumoksid, hafnium oxide, hafnium tetrachloride, "
            "hafniumtetraklorid, HfO2, HfCl4, hafnium carbide, hafniumkarbid"
        ),
        "8112.92",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C002.b.4",
        "Niob-/niobumlegeringer",
        "Wassenaar",
        "7440-03-1, 7718-54-9, 10099-58-8",
        (
            "niobium, columbium, niob, niobium pentachloride, niobiumklorid, "
            "niobium oxide, niobiumoksid, Nb, NbCl5, Nb2O5"
        ),
        "8112.92",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C002.b.6",
        "Reniummetall, legeringer og forbindelser",
        "Wassenaar",
        "7440-15-5, 10580-52-6, 14762-37-9",
        ("rhenium, renium, rhenium powder, reniumpulver, perrhenic acid, rhenium oxide, reniumoksid, Re"),
        "2615.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C002.b.7",
        "Germaniummetall og forbindelser",
        "Wassenaar",
        "7440-56-4, 1310-53-8, 10038-98-9, 10529-52-9",
        ("germanium, germaniumdioksid, germanium dioxide, GeO2, germanium tetrachloride, germaniumtetraklorid, GeCl4"),
        "2804.60, 8112.92",
    ),
    # ══ Spesifikke metaller (1C011) — Wassenaar/NSG ══════════════════════════
    _Item(
        "II",
        "1",
        "C",
        "1C011.a",
        "Berylliummetall, legeringer og forbindelser",
        "Wassenaar",
        "7440-41-7, 1304-56-9, 7787-49-7, 66104-24-3",
        (
            "beryllium, beryll, berylliumoksid, beryllium oxide, BeO, "
            "beryllium fluoride, berylliumfluorid, BeF2, beryllium copper, "
            "berylliumkobber, BeCu, beryllium powder, berylliumpulver"
        ),
        "8112.12, 8112.19",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C011.b",
        "Zirkoniummetall, legeringer og forbindelser (med lav hafniuminnhold)",
        "NSG",
        "7440-67-7, 7699-43-6, 13746-89-9",
        (
            "zirconium, zirkonium, zirconium oxychloride, zirkoniumoksyklorid, "
            "ZrOCl2, zirconium tetrachloride, Zr, reactor grade zirconium, "
            "kjernemateriale-zirkonium"
        ),
        "8109.20, 8109.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C011.c",
        "Magnesiummetall (høyrent, >99,7 %)",
        "Wassenaar",
        "7439-95-4",
        ("magnesium, magnesiummetall, high purity magnesium, høyrent magnesium, magnesium powder, magnesiumpulver, Mg"),
        "8104.11, 8104.19",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C011.d",
        "Litium anriket i Li-6 isotop",
        "NSG",
        "14258-74-3",
        ("lithium-6, litium-6, Li-6, enriched lithium, lithium isotope, litiumisotop, nuclear lithium, kjernelitium"),
        "2805.12",
    ),
    # ══ Nukleære materialer (1C232–1C234) — NSG ══════════════════════════════
    _Item(
        "II",
        "1",
        "C",
        "1C232.a",
        "Tritium — kjernefysisk isotop",
        "NSG",
        "10028-17-8",
        ("tritium, T, hydrogen-3, tritium gas, tritiumgass, radioaktivt hydrogen, heavy hydrogen isotope"),
        "2844.40",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C232.b",
        "Uran — naturlig, lavberiket og utarmet",
        "NSG",
        "7440-61-1, 10049-14-6, 7783-81-5, 7791-26-6",
        (
            "uranium, uran, UF6, uranium hexafluoride, uraniumheksafluorid, "
            "LEU, low enriched uranium, DU, depleted uranium, utarmet uran, "
            "UO2, uranium oxide, uraniumoksid, enriched uranium, beriket uran"
        ),
        "2844.10, 2844.20, 2844.30",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C233",
        "Litium-6 — nukleært brensel",
        "NSG",
        "14258-74-3",
        "lithium-6, litium-6, Li-6, nuclear fuel, kjernebrensel, tritium producer",
        "2805.12",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C234",
        "Hafnium (kjernekvalifisert) — reaktorabsorbent",
        "NSG",
        "7440-58-6",
        (
            "hafnium, nuclear grade hafnium, kjernekvalifisert hafnium, "
            "reactor hafnium, reaktorhafnium, neutron absorber, nøytronabsorbent"
        ),
        "8112.92",
    ),
    # ══ Eksplosiver og drivstoff (1C111) — MTCR/Wassenaar ════════════════════
    _Item(
        "II",
        "1",
        "C",
        "1C111.a.1",
        "Ammoniumperklorat — fast rakettdrivstoff",
        "MTCR",
        "7790-98-9",
        (
            "ammonium perchlorate, ammoniumperklorat, AP, "
            "perchloric acid ammonium salt, solid rocket propellant, "
            "faststoff-drivstoff, APCP"
        ),
        "2829.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C111.a.2",
        "HMX (oktogen) — militært sprengstoff",
        "Wassenaar",
        "2691-41-0",
        (
            "HMX, octogen, oktogen, homocyclonite, "
            "cyclotetramethylene-tetranitramine, tetrahexamine tetranitrate, "
            "octahydro-1,3,5,7-tetranitro-1,3,5,7-tetrazocine"
        ),
        "2910.90, 3602.00",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C111.a.3",
        "RDX (heksogen) — militært sprengstoff",
        "Wassenaar",
        "121-82-4",
        (
            "RDX, hexogen, heksogen, cyclonite, T4, "
            "cyclotrimethylene-trinitramine, hexahydro-1,3,5-trinitro-1,3,5-triazine, "
            "research department explosive, cyclotrimethylenetrinitramine"
        ),
        "2910.90, 3602.00",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C111.a.4",
        "TNT (trinitrotoluen) — sprengstoff",
        "Wassenaar",
        "118-96-7",
        ("TNT, trinitrotoluene, trinitrotoluen, trotyl, 2,4,6-trinitrotoluene, trilite, trinol"),
        "2904.20, 3602.00",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C111.a.5",
        "PETN (pentaerytritoltetranitrat) — sprengstoff",
        "Wassenaar",
        "78-11-5",
        (
            "PETN, pentaerythritol tetranitrate, pentaerytritoltetranitrat, "
            "penthrite, penta, nitropenta, pentrite, PENTA"
        ),
        "2910.90, 3602.00",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C111.b.1",
        "HTPB — drivstoff-bindemiddel for raketter",
        "MTCR",
        "69102-90-5",
        (
            "HTPB, hydroxyl-terminated polybutadiene, hydroksylterminert polybutadien, "
            "hydroxy-terminated polybutadiene, solid propellant binder, drivstoffbindemiddel"
        ),
        "3909.50",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C111.c.1",
        "Nitrocellulose (høynitret, >12,5 % N)",
        "Wassenaar",
        "9004-70-0",
        ("nitrocellulose, nitroc, NC, cellulose nitrate, gun cotton, kruttpamull, collodion, pyroxylin"),
        "3601.00, 3604.90, 3906.90",
    ),
    # ══ Rakettdrivstoff — 1C210 (MTCR-kontrollert for rakettrekkevidde) ══════
    _Item(
        "II",
        "1",
        "C",
        "1C210.a",
        "Ammoniumperklorat — rakettdrivstoff (1C210)",
        "MTCR",
        "7790-98-9",
        (
            "ammonium perchlorate, ammoniumperklorat, solid propellant, "
            "faststoff-drivstoff, rocket motor propellant, rakettdrivstoff"
        ),
        "2829.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C210.b",
        "HTPB — rakettdrivstoff-bindemiddel (1C210)",
        "MTCR",
        "69102-90-5",
        (
            "HTPB, hydroxyl terminated polybutadiene, hydroksylterminert polybutadien, "
            "binder for solid propellant, solid rocket binder"
        ),
        "3909.50",
    ),
    # ══ CWC Schedule 2/3 kjemiske forløpere (1C350) — Australia Group ════════
    _Item(
        "II",
        "1",
        "C",
        "1C350.1",
        "Tiodiglykol — sennepsgass-forløper",
        "Australia Group",
        "111-48-8",
        (
            "thiodiglycol, tiodiglykol, 2,2'-thiodiethanol, "
            "bis(2-hydroxyethyl)sulfide, bis(2-hydroxyethyl)sulphide, "
            "mustard precursor, sennepsgass-forløper, TDG"
        ),
        "2930.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.3",
        "PFIB — toksisk gass",
        "Australia Group",
        "382-21-8",
        (
            "PFIB, perfluoroisobutylene, perfluorisobutylen, "
            "1,1,3,3,3-pentafluoro-2-(trifluoromethyl)-1-propene, "
            "perfluoroisobutene"
        ),
        "2903.79",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.5",
        "Fosfortriklorid — nervegass-forløper",
        "Australia Group",
        "7719-12-2",
        (
            "phosphorus trichloride, fosforklorid, fosfortriklorid, PCl3, "
            "trichlorophosphine, triklorofosfin, phosphorous trichloride"
        ),
        "2812.10",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.12",
        "Trietanolamin — sennepsgass-forløper",
        "Australia Group",
        "102-71-6",
        ("triethanolamine, trietanolamin, TEA, tris(2-hydroxyethyl)amine, triethanol amine, TEOA"),
        "2922.13",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.14",
        "Trietylamin",
        "Australia Group",
        "121-44-8",
        ("triethylamine, trietylamin, TEA, N,N-diethylethanamine, triethyl amine"),
        "2921.19",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.18",
        "Pinakolylalkohol — soman-forløper",
        "Australia Group",
        "464-07-3",
        (
            "pinacolyl alcohol, pinakolylalkohol, pinacol, "
            "3,3-dimethyl-2-butanol, 1,2-dimethyl-1-propanol, "
            "soman precursor, soman-forløper, GD precursor"
        ),
        "2905.19",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.22",
        "QL — VX nervegass-forløper",
        "Australia Group",
        "57856-11-8",
        ("QL, O-Ethyl O-2-diisopropylaminoethyl methylphosphonite, VX precursor, VX-forløper, ethyl methylphosphonite"),
        "2931.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.28",
        "Metylfosfonylklorid (DC) — nervegass-forløper",
        "Australia Group",
        "676-97-1",
        (
            "methylphosphonic dichloride, metylfosfondiklorid, "
            "methylphosphonyl dichloride, DC, methyl phosphonic dichloride, "
            "nerve agent precursor, nervegass-forløper, MPC"
        ),
        "2931.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.36",
        "Dimetylmetylfosfonat (DMMP)",
        "Australia Group",
        "756-79-6",
        (
            "dimethyl methylphosphonate, DMMP, dimetylmetylfosfonat, "
            "methyl phosphonic acid dimethyl ester, fire retardant simulant"
        ),
        "2931.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.57",
        "Trimetylfosfitt — syntetisk forløper",
        "Australia Group",
        "121-45-9",
        ("trimethyl phosphite, trimetylfosfitt, phosphorous acid trimethyl ester, TMP, trimethoxyphosphine"),
        "2920.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C350.59",
        "Diklordifenyltriklormetan (DDT) og analoge — ikke kontrollert",
        "Australia Group",
        "107-49-3",
        ("TEPP, tetraethyl pyrophosphate, tetraetylpyrofosfat, diphosphoric acid tetraethyl ester"),
        "2931.90",
    ),
    # ══ 1C450: Toksiske kjemikalier (Australia Group) ═════════════════════════
    _Item(
        "II",
        "1",
        "C",
        "1C450.a.1",
        "Amiton — obsolet plantevernmiddel/nervegass",
        "Australia Group",
        "78-53-5",
        ("amiton, VG, O,O-Diethyl S-[2-(diethylamino)ethyl] phosphorothioate, tetram"),
        "2931.90",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C450.a.5",
        "BZ — inkapasiteringsmiddel",
        "Australia Group",
        "6581-06-2",
        ("BZ, 3-quinuclidinyl benzilate, QNB, agent BZ, incapacitating agent, inkapasiteringsmiddel"),
        "2933.39",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C450.a.7",
        "Dimetylsulfat — toksisk alkylerende stoff",
        "Australia Group",
        "77-78-1",
        ("dimethyl sulfate, dimetylsulfat, methyl sulfate, DMS, sulfuric acid dimethyl ester, dimethyl sulphate"),
        "2920.19",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C450.b.1",
        "Hydrogencyanid (prusisk syre)",
        "Australia Group",
        "74-90-8",
        ("hydrogen cyanide, hydrogencyanid, prussic acid, prusisk syre, HCN, formonitrile, blåsyre"),
        "2837.11, 2837.19",
    ),
    _Item(
        "II",
        "1",
        "C",
        "1C450.b.3",
        "Fosgen (karbonylklorid)",
        "Australia Group",
        "75-44-5",
        ("phosgene, fosgen, carbonyl chloride, karbonylklorid, COCl2, carbon oxychloride"),
        "2812.10",
    ),
    # ══ ML7: Kjemiske og biologiske stridsmidler (Vareliste I) ════════════════
    _Item(
        "I",
        "ML7",
        None,
        "ML7.a.1",
        "Kjemisk stridsmiddel — sarin (GB)",
        "CWC/OPCW",
        "107-44-8",
        (
            "sarin, GB, O-isopropyl methylphosphonofluoridate, "
            "isopropyl methylphosphonofluoridate, nervegass, nerve agent, "
            "GB nerve agent, Schedule 1 chemical"
        ),
        None,
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.a.2",
        "Kjemisk stridsmiddel — soman (GD)",
        "CWC/OPCW",
        "96-64-0",
        (
            "soman, GD, pinacolyl methylphosphonofluoridate, "
            "1,2,2-trimethylpropyl methylphosphonofluoridate, "
            "nervegass, nerve agent, GD nerve agent, Schedule 1 chemical"
        ),
        None,
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.a.3",
        "Kjemisk stridsmiddel — tabun (GA)",
        "CWC/OPCW",
        "77-81-6",
        (
            "tabun, GA, ethyl N,N-dimethylphosphoramidocyanidate, "
            "dimethylphosphoramidocyanidic acid ethyl ester, "
            "nervegass, nerve agent, GA nerve agent, Schedule 1 chemical"
        ),
        None,
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.a.4",
        "Kjemisk stridsmiddel — VX",
        "CWC/OPCW",
        "50782-69-9",
        (
            "VX, O-ethyl S-[2-(diisopropylamino)ethyl] methylphosphonothioate, "
            "ethyl {[2-(diisopropylamino)ethyl]sulfanyl}(methyl)phosphinate, "
            "VX nerve agent, nervegass, Schedule 1 chemical"
        ),
        None,
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.a.5",
        "Kjemisk stridsmiddel — sennepsgass (HD)",
        "CWC/OPCW",
        "505-60-2",
        (
            "mustard gas, sennepsgass, HD, sulfur mustard, "
            "bis(2-chloroethyl)sulfide, yperite, yellow cross, "
            "di-2-chloroethyl sulfide, blister agent, vesikant, "
            "Schedule 1 chemical"
        ),
        None,
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.a.6",
        "Kjemisk stridsmiddel — lewisitt",
        "CWC/OPCW",
        "541-25-3",
        (
            "lewisite, lewisitt, L, 2-chlorovinyldichloroarsine, "
            "chlorovinyldichloroarsine, arsenblæremiddel, arsenic blister agent, "
            "Schedule 1 chemical"
        ),
        None,
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.a.7",
        "Kjemisk stridsmiddel — fosgènoksim (CX)",
        "CWC/OPCW",
        "1794-86-1",
        (
            "phosgene oxime, fosgènoksim, CX, dichloroformaldoxime, "
            "nettle agent, blister agent, urticant, Schedule 1 chemical"
        ),
        None,
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.c.1",
        "Biologisk agens — miltbrannsporer (Bacillus anthracis)",
        "CWC/BWC",
        None,
        (
            "anthrax, antraks, bacillus anthracis, biological weapon, "
            "biologisk stridsmiddel, weaponized spores, milzbrand"
        ),
        None,
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.f.1",
        "Tåregass — CS-gass (klorbenzylidenmalononitril)",
        "Wassenaar",
        "2698-41-5",
        (
            "CS gas, CS, tåregass, tear gas, 2-chlorobenzalmalononitrile, "
            "chlorobenzalmalononitrile, riot control agent, opprørskontrollmiddel"
        ),
        "2926.90",
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.f.2",
        "Tåregass — OC-spray / pepperspray",
        "Wassenaar",
        "404-86-4",
        (
            "capsaicin, OC spray, pepper spray, pepperspray, "
            "oleoresin capsicum, riot control agent, opprørskontrollmiddel, "
            "PAVA, pelargonic acid vanillylamide"
        ),
        "2939.99",
    ),
    _Item(
        "I",
        "ML7",
        None,
        "ML7.f.3",
        "Tåregass — CN-gass (klloracetofenon)",
        "Wassenaar",
        "532-27-4",
        ("CN gas, CN, chloroacetophenone, kloracetofenon, mace, tear gas, tåregass, riot control agent"),
        "2914.79",
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Import-logikk
# ─────────────────────────────────────────────────────────────────────────────


async def _run(dry_run: bool) -> None:
    from app.core.database import get_session_factory
    from app.services.export_control_service import upsert_item

    created = updated = 0

    if dry_run:
        print(f"[DRY-RUN] Ville importert {len(_ITEMS)} kjemikalier (kilde='{SOURCE_VERSION}').")
        for it in _ITEMS:
            print(f"  {it.item_code:30s} | {it.title[:60]}")
        return

    async with get_session_factory()() as session:
        for it in _ITEMS:
            is_new = await upsert_item(
                session,
                list_code=it.list_code,
                category=it.category,
                group=it.group,
                item_code=it.item_code,
                title=it.title,
                regime=it.regime,
                source_version=SOURCE_VERSION,
                cas_numbers=it.cas_numbers,
                synonyms=it.synonyms,
                hs_codes=it.hs_codes,
            )
            created += int(is_new)
            updated += int(not is_new)
        await session.commit()

    print(f"Ferdig: {created} nye, {updated} oppdatert ({created + updated} totalt, kilde='{SOURCE_VERSION}').")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed kjemikaliedata i eksportkontroll-databasen")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Vis hva som ville bli importert uten å skrive til databasen",
    )
    args = ap.parse_args()
    asyncio.run(_run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
