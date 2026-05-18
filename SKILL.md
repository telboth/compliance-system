# XLENT Compliance — Prosjektkontekst

Bruk denne filen som bakgrunn når du jobber med kode, arkitektur eller innhold relatert til XLENT Compliance-prosjektet. Den gir deg den konteksten du trenger for å ta gode beslutninger uten å måtte spørre om grunnleggende ting.

---

## Hvem vi er

**XLENT Norge AS** (xlent.no) er et norsk konsulentselskap med fokus på teknologi, data og digitalisering. Vi selger konsulenttjenester — ikke produkter. Teamet som jobber med dette prosjektet ledes av Thomas Elboth, senior data scientist med PhD i anvendt matematikk og bakgrunn fra signalbehandling og marin seismikk (Shearwater/PGS). Han har tung erfaring med anomali-deteksjon på støyende data, som er direkte overførbart til compliance-domenet.

Vi er et lite team som bygger en ny tjeneste. Vi er ikke et produktselskap med 50 utviklere. Kode skal være pragmatisk, lesbar og vedlikeholdbar — ikke overdesignet.

---

## Hva vi bygger

**XLENT Compliance** er en AI-drevet tjeneste som automatiserer compliance-kontroll for norske eksportbedrifter. Kjernen er:

1. **Invoice-analyse:** Vi leser invoices (PDF-er) med Dokument-AI (OCR + LLM) og ekstraherer strukturerte felter med konfidensscore.
2. **Sanksjonsscreening:** Vi sjekker alle entiteter (kjøper, selger, sluttbruker, leveringsadresse) mot sanksjonslister (UN, EU, OFAC, norske lister) via OpenSanctions yente (self-hosted, MIT).
3. **Regelmotor:** Konfigurerbare regler i YAML — landrestriksjoner, beløpsgrenser, produktbegrensninger, dual-use-flagging. Controllere og compliance officers kan redigere regler uten kode.
4. **Rammeavtale-matching:** LLM parser rammeavtaler (PDF) til strukturert JSON og sjekker invoices mot avtalebetingelser (pris, produkter, geografi, volum).
5. **Review-arbeidsflate:** Controllere behandler flaggede invoices daglig — med all kontekst i ett bilde og obligatorisk begrunnelse.
6. **Audit-logg:** Hash-kjedet, append-only logg over alle beslutninger. Revisjonsspor for Tolletaten, revisor og forsikring.

Utfall per invoice: **grønt** (godkjent), **gult** (advarsel — krever menneskelig review), **rødt** (blokkert).

---

## Hvilket problem vi løser

Norske eksportbedrifter som selger avansert teknisk utstyr globalt har et compliance-problem som har eskalert kraftig siden 2022:

- **Regulatorisk press:** EUs sanksjonsregime mot Russland oppdateres kontinuerlig. Eksportkontrolloven med dual-use-lister. CSDDD (EUs forsyningskjede-direktiv). Skjerpede krav til sluttbrukererklæringer.
- **Konsekvens ved feil:** Kongsberg Automotive ble politianmeldt i 2025 etter at bildeler for 33 MNOK ble videresolgt til Russland via Tyrkia. Kongsberg Gruppen fikk undervannsteknologi videresolgt til russisk militært lyttesystem via Kypros. Bøter, straffansvar, omdømmetap.
- **Operativ virkelighet:** Mye compliance-arbeid skjer manuelt. Volumet av invoices er for stort til full kontroll. Rammeavtaler er PDF-er som ikke er enkelt maskinleselige. Rescreening av eksisterende kunder skjer sjelden.

Controllere i disse bedriftene bruker timer på manuell gjennomgang som kan automatiseres. CFO-er og juridiske direktører er kjøperne — de kjøper risikoreduksjon, ikke effektivitet.

---

## Strategisk posisjonering

Vi selger **plattform + tilpasning** — ikke ren konsulent, ikke ren SaaS:

- 60–70 % av leveransen er gjenbrukbar plattform-kjerne
- Resten tilpasses per kunde (regler, avtaler, integrasjoner, rapportformat)
- Konsulentdelen (onboarding, rammeavtale-strukturering, regelkonfigurasjon) rettferdiggjør prisen og skaper kundelås

**Vår edge mot ferdigpakkede løsninger:** Ingen av de etablerte (Dow Jones, ComplyAdvantage, Descartes, AEB) gjør rammeavtale-matching, graf-basert anomali-deteksjon, eller integrert invoice-analyse tilpasset norske eksportbedrifter. De screener mot lister — vi kobler invoices til kontekst, avtaler og mønstre over tid.

---

## Målgruppe

Typisk kunde: norsk selskap som selger avansert teknisk utstyr globalt. Bransjer: O&G, maritim, forsvar, prosessindustri, avansert produksjon. Ikke nødvendigvis store i antall ansatte, men ofte stor omsetning. Rammeavtaler med 20–200 kunder. Service og reparasjon på eksisterende utstyr.

Kjøper: CFO eller juridisk direktør. Daglig bruker: controller eller compliance officer.

---

## Teknisk stack

| Lag | Teknologi | Kommentar |
|-----|-----------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic | Async, Pydantic v2 |
| Database | PostgreSQL 16 | All strukturert data, ingen grafbase i MVP |
| LLM (sky) | Anthropic Claude (primær), OpenAI GPT-4o (backup) | Abstraksjonslag som gjør det enkelt å bytte |
| LLM (on-prem, fase 2) | Llama 3 / Mistral via vLLM | For kunder som ikke kan sende data til sky |
| Sanksjonsdata | OpenSanctions yente (self-hosted, MIT) | Gratis gratislister (UN, EU, OFAC) + OpenSanctions aggregering |
| PDF-parsing | pdfplumber (digitale), Tesseract (skannet) | Autodeteksjon |
| Oppgavekø | Celery + Redis | Asynkron invoice-prosessering |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS | TanStack Query + Table |
| Infrastruktur | Docker Compose, Nginx | Én maskin for MVP |

---

## Arkitekturprinsipper

Disse prinsippene skal følges i all kode:

1. **LLM beslutter aldri alene.** Dokument-AI ekstraherer felter. Regelmotoren beslutter. LLM-en forbereder data og forklarer beslutninger — men tar ikke juridiske avgjørelser. Hallusinering i compliance er en katastrofe.

2. **Konfidens er eksplisitt.** Hvert ekstrahert felt har en konfidensscore. Alt under 0.8 eskaleres til manuell review. Aldri still inn noe som sikkert når det ikke er det.

3. **Audit-loggen er hellig.** Append-only, hash-kjedet. Ingen UPDATE, ingen DELETE. Hvem så hva, når, hvilken regelversjon, hvilken beslutning, hvilken begrunnelse. Denne tabellen er det jurister og revisorer ser på.

4. **Regler er versjonert.** Hver regelendring logges med tidsstempel, bruker og grunn. Test-modus lar deg kjøre regler mot historiske invoices før aktivering.

5. **LLM-abstraksjonen er obligatorisk.** All LLM-kommunikasjon går via et abstraksjonslag (ABC-basert) som lar oss bytte mellom Claude, GPT-4o og lokal modell uten å endre forretningslogikk.

6. **Asynkront fra start.** Invoice-opplasting returnerer umiddelbart. Prosessering (parsing → ekstraksjon → screening → regler) kjører i bakgrunn via Celery. Frontend poller eller bruker WebSocket for statusoppdatering.

7. **Ikke bygg det du ikke trenger ennå.** Kunnskapsgraf, RAG, graf-anomali, on-prem LLM, læringsløkker — alt dette er fase 2+. MVP-en skal demonstrere verdi med invoice-analyse, sanksjonsscreening, regelmotor og review-UI.

---

## GDPR-compliance

XLENT Compliance behandler invoices som inneholder personopplysninger (navn, adresser, kontaktpersoner). Løsningen skal være GDPR-compliant fra dag én. Dette er ikke noe som legges til etterpå.

### Behandlingsgrunnlag

- **Berettiget interesse** (Art. 6(1)(f)): Compliance-kontroll er en lovpålagt forpliktelse for eksportbedrifter. Behandling av persondata i invoices er nødvendig for å overholde sanksjonsregelverk og eksportkontrollov.
- **Rettslig forpliktelse** (Art. 6(1)(c)): Regnskapsloven krever oppbevaring av fakturaer i 5 år (tillegg: 7 år for bokføringspliktige).
- Sanksjonsscreening av personer er nødvendig for å overholde EU-sanksjonsforordninger og norsk sanksjonslovgivning.

### Krav som skal implementeres i kode

1. **Dataminimering.** Ekstraher og lagre kun felter som er nødvendige for compliance-vurderingen. Ikke lagre hele PDF-teksten permanent hvis det ikke trengs etter prosessering. Definer eksplisitt hvilke felter som lagres og hvorfor.

2. **Konfigurerbar lagringstid.** Hver datatype har en definert lagringstid. Default: 7 år for invoices og beslutninger (regnskapsloven). Kortere for mellomresultater (f.eks. rå LLM-output). Automatisk sletting via periodisk Celery-task.

3. **Rett til innsyn og sletting.** Endepunkt `GET /api/gdpr/export/{entity_id}` returnerer all data knyttet til en person eller kunde. Endepunkt `DELETE /api/gdpr/erase/{entity_id}` sletter persondata, men beholder anonymisert audit-logg (juridisk nødvendig). Sletteforespørsler logges.

4. **Databehandleravtaler (DPA).** Kreves for alle sky-tjenester som behandler persondata: LLM-leverandør (Anthropic/OpenAI), hosting-leverandør, eventuelt OpenSanctions. Dokumenter hvem som er databehandler og hvilke data de mottar.

5. **Data i transitt og i ro.** TLS 1.3 for all API-kommunikasjon. AES-256 kryptering for lagrede PDF-er og sensitive felter i databasen. Krypteringsnøkler håndtert via miljøvariabler, aldri i kode.

6. **Logging av tilgang.** All tilgang til persondata logges i audit-loggen. Hvem så hvilke data, når, og hvorfor. Dette er påkrevd for å kunne svare på tilsynsmyndighetenes forespørsler.

7. **On-prem alternativ.** Noen kunder vil kreve at persondata aldri forlater deres infrastruktur. Arkitekturen må støtte on-prem deploy med lokal LLM (Llama/Mistral) som alternativ til sky-basert LLM. Dette er fase 2, men arkitekturen må tilrettelegge for det fra start (LLM-abstraksjonslaget).

### Kode-konvensjon for GDPR

- Merk funksjoner som behandler persondata med docstring som forklarer behandlingsgrunnlaget.
- Bruk en `@personal_data`-dekoratør (eller tilsvarende) som logger tilgangen automatisk.
- Aldri logg persondata i klartekst til applikasjonslogger. Bruk pseudonymiserte identifikatorer.
- Konfigurer lagringstid per modell via en sentral `retention_policy.py`.

---

## EU AI Act

EU AI Act (Regulation 2024/1689) er verdens første omfattende AI-regulering. Krav for høyrisiko-AI-systemer trer i kraft fra august 2026 (mulig utsatt til desember 2027 via Omnibus-forslaget, men dette er ikke bekreftet per mai 2026). XLENT Compliance bruker AI til å ta beslutninger som har juridisk konsekvens (blokkere transaksjoner, flagge sanksjonsbrudd), og må derfor ta hensyn til AI Act fra start.

### Risikoklassifisering

XLENT Compliance er sannsynligvis **ikke** et høyrisiko-system per Annex III (som primært dekker biometri, kritisk infrastruktur, utdanning, ansettelse, kredittvurdering, rettshåndhevelse og migrasjon). Men: systemet tar beslutninger som påvirker bedrifters evne til å handle, og kan blokkere transaksjoner. Avhengig av kundens bruk kan det falle inn under «AI-systemer brukt til å vurdere kredittverdighet eller etablere kredittscore» (Annex III punkt 5b) hvis kunden bruker det til leverandør- eller kundevurdering.

**Uavhengig av klassifisering bør vi følge prinsippene for høyrisiko-systemer**, fordi: (a) det styrker tilliten hos kunder og revisorer, (b) det gjør eventuell fremtidig klassifisering smertefri, og (c) det er rett og slett god praksis for et system som tar compliance-beslutninger.

### Krav vi implementerer

1. **Risikostyringssystem (Art. 9).** Dokumenter hvilke risikoer AI-komponentene introduserer (hallusinering, bias, falske negativer) og hvilke tiltak som reduserer dem. Oppdater dette løpende. I kode: en `RISK_REGISTER.md` i repoet som oppdateres ved vesentlige endringer.

2. **Data governance (Art. 10).** Sørg for at treningsdata og kontekstdata (sanksjonslister, avtaletekster) er relevante, representative og så frie for feil som mulig. Dokumenter datakildene, oppdateringsfrekvens, og kvalitetskontrolltiltak. I kode: hver sanksjonsliste-loader har en `data_quality_check()`-funksjon som validerer innholdet etter nedlasting.

3. **Teknisk dokumentasjon (Art. 11).** Systemet skal ha tilstrekkelig dokumentasjon til at en tredjepart kan forstå hvordan det fungerer, hvilke data det bruker, og hvordan beslutninger tas. I praksis: arkitekturdokumentasjon, API-dokumentasjon (auto-generert via FastAPI/OpenAPI), og forklarende kommentarer i koden.

4. **Automatisk hendelseslogging (Art. 12).** Systemet skal automatisk logge hendelser som er relevante for å identifisere risiko — inkludert alle LLM-kall, screening-resultater, regelutfall, og beslutninger. Vår hash-kjedede audit-logg dekker dette.

5. **Transparens og informasjon (Art. 13).** Brukere (controllere) skal forstå hvordan systemet fungerer og hva det baserer sine anbefalinger på. Hver beslutning skal ha en sporbar begrunnelse som refererer til konkrete regler, lister og data. Ingen «svarte bokser».

6. **Menneskelig tilsyn (Art. 14).** Et menneske skal alltid ha mulighet til å overstyre systemet. Gult og rødt flagg krever menneskelig review. Grønne kan auto-godkjennes, men skal kunne overprøves. Systemet skal aldri blokkere en transaksjon uten at et menneske kan oppheve blokkeringen.

7. **Nøyaktighet, robusthet og cybersikkerhet (Art. 15).** Mål og dokumenter nøyaktighet (precision, recall, falsk-positive-rate) på testdata. Implementer fallback-mekanismer ved LLM-feil. Sikre mot adversarial input (manipulerte invoices designet for å omgå screening).

### Kode-konvensjon for AI Act

- Alle LLM-kall logges med input, output, modellversjon, og timestamp.
- Beslutningsbegrunnelser er strukturerte (JSON med regel-ID, matchede entiteter, konfidensverdier), ikke fritekst.
- `TECHNICAL_DOCUMENTATION.md` i repoet beskriver systemet i henhold til Art. 11-kravene.
- Funksjoner som implementerer menneskelig tilsyn (override, eskalering) skal være tydelig merket og aldri kunne deaktiveres via konfigurasjon.
- Nøyaktighetsmålinger kjøres som del av CI/CD-pipeline mot et fastlagt testsett.

---

## Datamodell — nøkkelentiteter

```
invoices ──< invoice_lines
    │
    ├──< entities ──< screening_results
    │
    ├──< extracted_fields
    │
    ├──< rule_results >── rules ──< rule_versions
    │
    ├──< agreement_check_results >── agreements
    │
    ├──< decisions
    │
    └──< audit_log (append-only, hash-kjedet)

customers ──< invoices
          ──< agreements

users ──< decisions
      ──< audit_log
```

---

## Sanksjonsdata — gratiskilder

Rådataene fra myndighetene er gratis:

| Kilde | Format | URL |
|-------|--------|-----|
| UN Consolidated List | XML | scsanctions.un.org |
| EU Financial Sanctions | XML feed | webgate.ec.europa.eu |
| US OFAC SDN List | CSV | treasury.gov/ofac/downloads |
| OFAC Consolidated | CSV | treasury.gov/ofac/downloads |
| Norsk sanksjonsliste | Via DEKSA | deksa.no |

**OpenSanctions** aggregerer 332+ kilder, dedupliserer og renser. Gratis for ikke-kommersiell bruk. Kommersiell lisens tilsvarer ca. én ingeniørdag per måned. Deres self-hosted matching-motor **yente** er MIT-lisensiert.

---

## Konkurranselandskap

| Kategori | Aktører | Hva de gjør | Hva de ikke gjør |
|----------|---------|-------------|-------------------|
| Sanksjonsscreening (SaaS) | Dow Jones, LSEG World-Check, ComplyAdvantage, LexisNexis | Screening mot lister, PEP, adverse media | Rammeavtale-matching, invoice-analyse |
| Trade compliance (plattform) | Descartes, AEB, S&P Global, Trademo | Eksportkontroll, lisenshåndtering, dokumentscreening | Graf-anomali, norsk tilpasning |
| ERP-moduler | SAP GTS, Oracle GTM | Integrert i ERP, sanksjon + eksportkontroll | Fleksibilitet, AI-basert ekstraksjon |

**Vår posisjon:** Vi kobler invoices til kontekst, avtaler og mønstre over tid. Ingen av de etablerte gjør alle tre.

---

## Nøkkelbegreper

- **Invoice:** Faktura — inngående eller utgående. Primærdokumentet vi analyserer. Vi bruker "invoice" konsekvent i kode og dokumentasjon.
- **Screening:** Sjekk av entiteter mot sanksjonslister. Returnerer match-score og kilde.
- **Trafikklys:** Grønt (godkjent), gult (advarsel, krever review), rødt (blokkert).
- **Regelmotor:** YAML-definerte regler med AND/OR/NOT-logikk. Versjonert, testbar.
- **Rammeavtale:** Kontrakt mellom bedrift og kunde som definerer tillatte produkter, geografi, volum og priser. Ofte en PDF på 30–50 sider.
- **Diversion:** Når varer videreselges til sanksjonerte land via tredjeland (f.eks. Tyrkia, Kypros, UAE).
- **Dual-use:** Varer som har både sivil og militær anvendelse. Regulert av eksportkontrolloven.
- **ECCN:** Export Control Classification Number — amerikansk klassifisering av kontrollvarer.
- **Yente:** OpenSanctions' self-hosted matching API. MIT-lisens. Fuzzy matching med konfigurerbar terskel.

---

## Faseinndeling

| Fase | Tidsramme | Fokus |
|------|-----------|-------|
| MVP (6 sprinter) | Uke 1–12 | Invoice-parsing, LLM-ekstraksjon, sanksjonsscreening, regelmotor, avtale-matching, review-UI, audit |
| Fase 2 | Mnd 4–6 | Kunnskapsgraf (Apache AGE), RAG-pipeline, eksportkontroll (ECCN), on-prem LLM |
| Fase 3 | Mnd 7–9 | Graf-anomali, læringsløkker, avansert rapportering |
| Fase 4 | Mnd 10–12 | Multi-tenant, bransje-pakker, API for tredjeparter |

---

## Kodestil, lesbarhet og dokumentasjon

Koden skal være **dokumenterbar og lesbar for mennesker**. Prioriter lesbar kode fremfor kompakt kode. Alltid. En kollega som leser koden om 6 måneder — eller en revisor som evaluerer compliance-systemet — skal kunne forstå hva som skjer uten å måtte dekompilere logikken mentalt.

### Prinsipper

- **Lesbarhet over kompakthet.** Skriv kode som forklarer seg selv. Hvis du kan velge mellom en one-liner og tre linjer som er lettere å forstå, velg tre linjer. List comprehensions er fine for enkle tilfeller, men nest ikke mer enn ett nivå.
- **Norsk i dokumentasjon, kommentarer og docstrings.** Engelsk i kode (variabelnavn, funksjonsnavn, klassenavn, commit-meldinger). Denne blandingen er bevisst: koden er teknisk og bør være søkbar på engelsk, men dokumentasjonen skal være tilgjengelig for alle i teamet og for kunder.
- **Type safety overalt.** Pydantic v2 for all input/output. TypeScript strict mode i frontend. Ingen `Any` uten god grunn og en kommentar som forklarer hvorfor.
- **Tester der det teller.** Test forretningslogikk (regelmotor, screening, beslutningsmotor, audit-logg). Ikke test boilerplate eller CRUD-operasjoner.
- **Logging, ikke print.** structlog i backend. Strukturerte logger som kan søkes i. Aldri logg persondata i klartekst.

### Kommentarer og docstrings

Alle moduler, klasser og funksjoner som inneholder forretningslogikk skal ha docstrings som forklarer:

```python
def screen_entity(entity: EntityInput) -> ScreeningResult:
    """
    Sjekker en entitet mot alle aktive sanksjonslister.

    Bruker OpenSanctions yente for fuzzy matching med konfigurerbar
    terskel (standard 0.7). Returnerer alle matcher over terskelen
    sortert etter score.

    Behandlingsgrunnlag GDPR: Berettiget interesse (Art. 6(1)(f)) —
    sanksjonsscreening er lovpålagt for eksportbedrifter.

    Args:
        entity: Entitetsdata med navn, type, land og rolle.

    Returns:
        ScreeningResult med match-liste, samlet status og tidsstempel.

    Raises:
        SanctionsListUnavailableError: Hvis sanksjonslisten ikke er
            oppdatert innen siste 48 timer.
    """
```

### Hva som skal kommenteres

- **Forretningslogikk:** Hvorfor denne regelen finnes, ikke bare hva den gjør. Referér til regelverk der relevant (f.eks. «Jf. OFAC 50%-regelen for eierskap»).
- **Compliance-kritiske steder:** Funksjoner som implementerer menneskelig tilsyn (Art. 14 EU AI Act), audit-logging, eller GDPR-relatert databehandling skal ha eksplisitte kommentarer om dette.
- **Ikke-åpenbare valg:** Hvorfor vi valgte en terskel på 0.7 for fuzzy matching, hvorfor vi hasher audit-loggen, hvorfor vi ikke bruker grafbase i MVP.
- **Avhengigheter mellom systemer:** Kommentarer som forklarer dataflyt mellom moduler (f.eks. «Denne funksjonen kalles av Celery-tasken process_invoice etter at LLM-ekstraksjon er fullført»).

### Hva som IKKE skal kommenteres

- Åpenbar kode som `i += 1` eller `return result`
- Boilerplate og CRUD-operasjoner med mindre det er noe uventet
- Selvforklarende variabelnavn — bruk heller bedre navn enn å legge til kommentarer

### Filstruktur og navngivning

- Én klasse per fil der det er naturlig. Ikke samle urelatert logikk i store filer.
- Funksjonsnavn skal beskrive hva de gjør: `screen_entities_against_sanctions()` er bedre enn `check()`.
- Konstanter i UPPER_CASE med kommentar: `CONFIDENCE_THRESHOLD = 0.8  # Felter under dette eskaleres til manuell review`
- Konfigurasjon samlet i `config.py` med Pydantic Settings — aldri hardkodede verdier i forretningslogikk.

### Repo-dokumentasjon

Følgende filer skal vedlikeholdes i repoets rot:

| Fil | Innhold |
|-----|---------|
| `README.md` | Prosjektbeskrivelse, oppsett, kjøring, arkitektur |
| `SKILL.md` | Denne filen — kontekst for AI-agenter og nye utviklere |
| `TECHNICAL_DOCUMENTATION.md` | Systemdokumentasjon ihht. EU AI Act Art. 11 |
| `RISK_REGISTER.md` | Risikoregister for AI-komponentene |
| `CHANGELOG.md` | Versjonert endringslogg |
| `docs/architecture.md` | Detaljert arkitekturdokumentasjon |
| `docs/api-reference.md` | API-dokumentasjon (supplement til auto-generert OpenAPI) |
| `docs/gdpr.md` | GDPR-behandlingsoversikt og databehandleravtaler |
| `docs/deployment.md` | Deploy- og driftsdokumentasjon |

---

*Sist oppdatert: 13. mai 2026. Internt dokument — XLENT Norge AS.*
