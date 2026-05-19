#!/usr/bin/env python3
"""Seed standard compliance-regler i databasen.

Kjør: docker compose exec api python scripts/seed_rules.py

Idempotent — regler som allerede eksisterer hoppes over.
Reglene dekker norsk eksportkontroll, EU-sanksjoner og interne rutiner.
"""

import asyncio
import sys

sys.path.insert(0, "/app")


DEFAULT_RULES = [
    # ── RED: Direkte embargo-treff ─────────────────────────────────────────────
    {
        "name": "Russland/Hviterussland embargo",
        "description": (
            "Blokkér forsendelser til eller via Russland/Hviterussland. "
            "EU totalembargo (forordning 2022/576) og norsk eksportkontrollregelverk."
        ),
        "severity": "red",
        "comment": "EU-forordning 2022/576, EØS-tilpasning i norsk eksportkontrollforskrift",
        "yaml": """\
name: Russland/Hviterussland embargo
description: Forsendelse til/fra Russland eller Hviterussland
severity: red
conditions:
  operator: OR
  rules:
    - field: destination_country
      op: in
      value: [RU, BY]
    - field: entities.country
      op: in
      value: [RU, BY]
""",
    },
    {
        "name": "Totalembargo-land (FN/EU/US)",
        "description": (
            "Forsendelse til land med internasjonalt totalembargo utover Russland/Hviterussland: "
            "Nord-Korea, Iran, Syria, Cuba, Myanmar, Libya, Somalia, Sør-Sudan, Sudan, "
            "Sentral-afrikanske republikk, Mali, Kongo, Jemen, Haiti, Afghanistan, Eritrea, "
            "Venezuela, Zimbabwe."
        ),
        "severity": "red",
        "comment": "FN Sikkerhetsrådets resolusjoner + EU/US sanksjonsregimer",
        "yaml": """\
name: Totalembargo-land (FN/EU/US)
description: Forsendelse til land med internasjonalt totalembargo
severity: red
conditions:
  operator: OR
  rules:
    - field: destination_country
      op: in
      value: [KP, IR, SY, CU, MM, LY, SO, SS, SD, CF, ML, CD, YE, HT, AF, ER, VE, ZW]
    - field: entities.country
      op: in
      value: [KP, IR, SY]
""",
    },
    {
        "name": "Sanksjonert selskap i parter",
        "description": (
            "Epostadresse eller selskapsnavn matcher kjente sanksjonerte russiske "
            "energiselskaper og statseide foretak (OFAC SDN / EU FSF)."
        ),
        "severity": "red",
        "comment": "Rosneft, Gazprom, Lukoil, Novatek, Surgutneftegas er på OFAC/EU-lister",
        "yaml": """\
name: Sanksjonert selskap i parter
description: Navn eller epost matcher sanksjonerte selskaper
severity: red
conditions:
  operator: OR
  rules:
    - field: entities.email
      op: regex
      value: "rosneft|gazprom|surgutneftegas|lukoil|novatek|transneft"
    - field: entities.name
      op: regex
      value: "(?i)(rosneft|gazprom|surgutneftegas|lukoil|novatek neftegas|transneft|vnesheconombank|sberbank|vtb bank)"
""",
    },
    {
        "name": "Militær varebeskrivelse",
        "description": (
            "En eller flere varelinjer inneholder begreper som indikerer militært materiell "
            "(våpen, sprengstoff, militærutstyr). Krever umiddelbar manuell gjennomgang."
        ),
        "severity": "red",
        "comment": "Norsk eksportkontrollforskrift §§ 3-4, Liste I og II",
        "yaml": """\
name: Militær varebeskrivelse
description: Varelinje inneholder militære nøkkelord
severity: red
conditions:
  operator: OR
  rules:
    - field: lines.description
      op: regex
      value: "(?i)(weapon|weapons|firearm|ammunition|ammo|explosive|warhead|missile|rocket|artillery|tank|armour|armor|military grade|combat|detonator|grenade|torpedo|bomb|gun powder)"
    - field: lines.product_code
      op: regex
      value: "(?i)(ML[0-9]|WA[0-9])"
""",
    },
    {
        "name": "Dual-use ECCN — eksportlisens kan kreves",
        "description": (
            "Varer med ECCN-kode som begynner med 1-9 (ikke EAR99) kan kreve eksportlisens "
            "ved eksport til ikke-allierte land. Gjelder dual-use-varer under EAR/EU DUR."
        ),
        "severity": "red",
        "comment": "EAR 15 CFR 774, EU Dual-Use-forordning 2021/821",
        "yaml": """\
name: Dual-use ECCN — eksportlisens kan kreves
description: ECCN-kode indikerer dual-use-vare til ikke-alliert destinasjon
severity: red
conditions:
  operator: AND
  rules:
    - field: lines.eccn
      op: regex
      value: "^[1-9][A-Z][0-9]"
    - field: destination_country
      op: not_in
      value: [NO, SE, DK, FI, DE, FR, GB, US, CA, AU, NZ, JP, KR, IL, AT, CH,
               AL, BE, BG, HR, CZ, EE, GR, HU, IS, IT, LV, LT, LU, ME, MK,
               NL, PL, PT, RO, SK, SI, ES]
""",
    },
    # ── GREEN/YELLOW: Informative og manuelle kontrollsignaler ────────────────
    {
        "name": "Forhøyet risiko: transittland for sanksjonsomgåelse",
        "description": (
            "Entiteter lokalisert i land som er kjent for å benyttes som transittland "
            "for sanksjonsomgåelse mot Russland: UAE, Kasakhstan, Armenia, Georgia, "
            "Aserbajdsjan, Usbekistan, Turkmenistan, Tadsjikistan, Kirgisistan. "
            "Regelen er informativ og skal ikke alene eskalere score."
        ),
        "severity": "green",
        "comment": "BIS Entity List-vurdering, EU-anneks XI forordning 2023/1214",
        "yaml": """\
name: "Forhøyet risiko: transittland for sanksjonsomgåelse"
description: Entiteter i kjente transittland for sanksjonsomgåelse
severity: green
conditions:
  operator: OR
  rules:
    - field: entities.country
      op: in
      value: [AE, KZ, AM, GE, AZ, UZ, TM, TJ, KG]
    - field: destination_country
      op: in
      value: [AE, KZ, AM, GE]
""",
    },
    {
        "name": "Manglende ECCN på utgående faktura",
        "description": (
            "Utgående faktura med varelinjer men uten ECCN-kode. "
            "ECCN er påkrevd for korrekt eksportkontroll-klassifisering."
        ),
        "severity": "yellow",
        "comment": "Internt krav, norsk eksportkontrollforskrift § 7",
        "yaml": """\
name: Manglende ECCN på utgående faktura
description: Ingen ECCN-kode registrert på utgående faktura
severity: yellow
conditions:
  operator: AND
  rules:
    - field: direction
      op: eq
      value: outgoing
    - field: lines.eccn
      op: not exists
      value: null
""",
    },
    {
        "name": "Manglende destinasjonsland på utgående faktura",
        "description": (
            "Utgående faktura uten destinasjonsland kan ikke risikovurderes korrekt. "
            "Feltet må fylles ut manuelt eller via re-ekstraksjon."
        ),
        "severity": "yellow",
        "comment": "Internt krav",
        "yaml": """\
name: Manglende destinasjonsland på utgående faktura
description: Destinasjonsland mangler på utgående faktura
severity: yellow
conditions:
  operator: AND
  rules:
    - field: direction
      op: eq
      value: outgoing
    - field: destination_country
      op: not exists
      value: null
""",
    },
    {
        "name": "MVA på eksportfaktura",
        "description": (
            "Utgående eksportfaktura inneholder MVA/VAT-beløp. "
            "Eksport er normalt 0-sats — dette kan indikere feilregistrering "
            "eller et rent innenlandsk salg som er feilklassifisert."
        ),
        "severity": "yellow",
        "comment": "Merverdiavgiftsloven § 6-21 (eksport — 0 %)",
        "yaml": """\
name: MVA på eksportfaktura
description: VAT-beløp registrert på utgående eksportfaktura
severity: yellow
conditions:
  operator: AND
  rules:
    - field: direction
      op: eq
      value: outgoing
    - field: total_amount
      op: gt
      value: 0
""",
    },
    {
        "name": "Manglende incoterms på utgående faktura",
        "description": (
            "Utgående faktura uten incoterms gjør det uklart hvem som har "
            "ansvar for eksportkontroll og tolldokumentasjon."
        ),
        "severity": "yellow",
        "comment": "Internt krav — Incoterms 2020",
        "yaml": """\
name: Manglende incoterms på utgående faktura
description: Incoterms mangler på utgående faktura
severity: yellow
conditions:
  operator: AND
  rules:
    - field: direction
      op: eq
      value: outgoing
    - field: incoterms
      op: not exists
      value: null
""",
    },
    {
        "name": "Stor transaksjon — forhøyet aktsomhet",
        "description": (
            "Faktura over EUR 100 000 utløser forhøyet aktsomhetsplikt "
            "etter hvitvaskingsloven § 17 og eksportkontrollregelverket."
        ),
        "severity": "yellow",
        "comment": "Hvitvaskingsloven § 17, terskel justert til EUR 100k internt",
        "yaml": """\
name: Stor transaksjon — forhøyet aktsomhet
description: Fakturabeløp over EUR 100 000
severity: yellow
conditions:
  operator: AND
  rules:
    - field: total_amount
      op: gte
      value: 100000
    - field: currency
      op: eq
      value: EUR
""",
    },
    {
        "name": "Dual-use ECCN 6A006 — presisjonsmåling",
        "description": (
            "Presisjonsmåleutstyr under ECCN 6A006 (akustiske systemer og relatert utstyr) "
            "krever eksportlisens til ikke-allierte land og kontroll mot sluttbrukererklæring."
        ),
        "severity": "yellow",
        "comment": "EAR 15 CFR 774, Seksjon 744 — Military End-Use Rule",
        "yaml": """\
name: Dual-use ECCN 6A006
description: ECCN 6A006 krever skjerpet kontroll mot sluttbrukererklæring
severity: yellow
conditions:
  operator: AND
  rules:
    - field: lines.eccn
      op: regex
      value: "^6A006"
    - field: destination_country
      op: not_in
      value: [NO, SE, DK, FI, DE, FR, GB, US, CA, AU, NZ, JP, KR, IL, AT, CH,
               AL, BE, BG, HR, CZ, EE, GR, HU, IS, IT, LV, LT, LU, ME, MK,
               NL, PL, PT, RO, SK, SI, ES]
""",
    },
]


async def seed() -> None:
    from app.core.database import get_session_factory
    from app.services.rule_engine_service import create_rule, list_rules

    async with get_session_factory()() as session:
        existing = await list_rules(session)
        existing_names = {r.name for r in existing}

        created = 0
        skipped = 0
        for rule_def in DEFAULT_RULES:
            if rule_def["name"] in existing_names:
                print(f"  SKIP  {rule_def['name']!r} (finnes allerede)")
                skipped += 1
                continue
            await create_rule(
                session,
                name=rule_def["name"],
                description=rule_def["description"],
                severity=rule_def["severity"],
                yaml_text=rule_def["yaml"],
                created_by="seed_script",
                comment=rule_def.get("comment"),
            )
            await session.commit()
            print(f"  OK    {rule_def['name']!r}")
            created += 1

        print(f"\nFerdig: {created} opprettet, {skipped} hoppet over.")


if __name__ == "__main__":
    asyncio.run(seed())
