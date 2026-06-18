# XLENT Compliance — MVP Byggeplan

**Versjon:** 1.0  
**Dato:** 13. mai 2026  
**Stack:** Python 3.12 / FastAPI / PostgreSQL / React / TypeScript  
**Tidsramme:** 12 uker (6 sprinter à 2 uker)  
**Demoklar:** Etter sprint 3 (uke 6)  
**Produksjonsklar MVP:** Etter sprint 6 (uke 12)

**Status:** Dette er en byggeplan og ikke en beskrivelse av dagens kode. For faktisk implementasjon, se `docs/architecture.md` og `docs/api-reference.md`.

---

## Innholdsfortegnelse

1. [Overordnet arkitektur](#1-overordnet-arkitektur)
2. [Teknisk stack](#2-teknisk-stack)
3. [Sprint 1 — Fundament](#3-sprint-1--fundament-uke-12)
4. [Sprint 2 — LLM-ekstraksjon](#4-sprint-2--llm-ekstraksjon-uke-34)
5. [Sprint 3 — Sanksjonsscreening](#5-sprint-3--sanksjonsscreening-uke-56)
6. [Sprint 4 — Regelmotor og avtaler](#6-sprint-4--regelmotor-og-avtaler-uke-78)
7. [Sprint 5 — Review-UI og audit](#7-sprint-5--review-ui-og-audit-uke-910)
8. [Sprint 6 — Integrasjon og hardening](#8-sprint-6--integrasjon-og-hardening-uke-1112)
9. [Datamodell](#9-datamodell)
10. [API-endepunkter](#10-api-endepunkter)
11. [Prosjektstruktur](#11-prosjektstruktur)
12. [Hva som bevisst er utelatt fra MVP](#12-hva-som-bevisst-er-utelatt-fra-mvp)
13. [Etter MVP — fase 2](#13-etter-mvp--fase-2)

---

## 1. Overordnet arkitektur

```
┌─────────────────────────────────────────────────────────────┐
│  INNGANG                                                     │
│  Invoice PDF → E-post / API / Filopplasting                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  DOKUMENT-AI                                                 │
│  pdfplumber / Tesseract → LLM-ekstraksjon → Strukturert JSON│
│  Konfidensscore per felt. Lav konfidens → manuell kø.        │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
┌─────────────┐ ┌───────────┐ ┌──────────────┐
│ Sanksjons-  │ │ Regel-    │ │ Avtale-      │
│ screening   │ │ motor     │ │ matching     │
│ (OpenSanc.) │ │ (YAML)    │ │ (LLM+regler)│
└──────┬──────┘ └─────┬─────┘ └──────┬───────┘
       │              │              │
       └──────────────┼──────────────┘
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  BESLUTNINGSMOTOR                                            │
│  Aggreger alle resultater → samlet compliance-score          │
│  Grønt (godkjent) / Gult (sjekk) / Rødt (blokker)          │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  REVIEW + AUDIT                                              │
│  Controller-arbeidsflate / Beslutning + begrunnelse          │
│  Audit-logg (append-only, hash-kjedet) / Rapporter           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Teknisk stack

### Backend

| Komponent | Teknologi | Versjon | Kommentar |
|-----------|-----------|---------|-----------|
| Web-rammeverk | FastAPI | 0.110+ | Async, Pydantic v2, OpenAPI docs |
| Database | PostgreSQL | 16 | Primær datalagring, all strukturert data |
| ORM | SQLAlchemy | 2.0 | Async sessions, Alembic for migrasjoner |
| PDF-parsing | pdfplumber | 0.11+ | Digitale PDF-er, tabellekstraksjon |
| OCR | Tesseract / pytesseract | 5.x | Skannet materiale, fallback |
| LLM (primær) | Anthropic Claude | claude-sonnet-4-20250514 | Invoice-ekstraksjon, avtaleparsing |
| LLM (alternativ) | OpenAI GPT-4o | gpt-4o | Backup, sammenligning |
| Sanksjonsdata | OpenSanctions yente | self-hosted | MIT-lisens, fuzzy matching |
| Oppgavekø | Celery | 5.4+ | Asynkron invoice-prosessering |
| Meldingsbroker | Redis | 7.x | Celery-broker + caching |
| Autentisering | fastapi-users + JWT | — | RBAC: controller, compliance, admin |
| Testing | pytest + httpx | — | Async test-klient mot FastAPI |

### Frontend

| Komponent | Teknologi | Versjon | Kommentar |
|-----------|-----------|---------|-----------|
| Rammeverk | React | 18+ | Funksjonelle komponenter, hooks |
| Språk | TypeScript | 5.x | Strict mode |
| Byggverktøy | Vite | 5.x | Rask HMR, god TypeScript-støtte |
| Styling | Tailwind CSS | 3.x | Utility-first, XLENT-fargepalett |
| State management | TanStack Query | 5.x | Server-state, caching, refetching |
| Tabeller | TanStack Table | 8.x | Sortering, filtrering, paginering |
| Skjema | React Hook Form + Zod | — | Validering, strukturerte skjema |
| Charts | Recharts | 2.x | Dashboard-grafer |
| Filopplasting | react-dropzone | 14.x | Drag-and-drop PDF-opplasting |

### Infrastruktur (MVP)

| Komponent | Teknologi | Kommentar |
|-----------|-----------|-----------|
| Kontainerisering | Docker Compose | postgres + api + worker + redis + frontend |
| Reverse proxy | Nginx | TLS-terminering, statiske filer |
| CI/CD | GitHub Actions | Lint, test, build, deploy |
| Hosting | Azure VM / AWS EC2 | Én maskin for MVP, skaler senere |

---

## 3. Sprint 1 — Fundament (uke 1–2)

**Mål:** En invoice-PDF kan lastes opp og parses til strukturerte felter.

### Backend-oppgaver

- [ ] Prosjektskjelett: FastAPI med async, Pydantic v2 modeller
- [ ] Docker Compose: `docker-compose.yml` med postgres, api, redis
- [ ] Alembic migrasjonsoppsett
- [ ] Datamodell: `invoices`, `invoice_lines`, `entities`, `customers`
- [ ] PDF-parser-modul:
  - `parsers/pdf_parser.py` — pdfplumber for digitale PDF-er
  - `parsers/ocr_parser.py` — Tesseract for skannet materiale
  - Autodeteksjon: prøv pdfplumber først, fall tilbake til OCR
- [ ] Endepunkt: `POST /api/invoices/upload` — mottar PDF, returnerer parsede felter
- [ ] Endepunkt: `GET /api/invoices/{id}` — hent invoice med alle felter
- [ ] Endepunkt: `GET /api/invoices` — liste med paginering og filtrering
- [ ] Helsesjekk: `GET /api/health`
- [ ] Grunnleggende feilhåndtering og logging (structlog)
- [ ] pytest oppsett med testdatabase og 5 test-invoices

### Frontend-oppgaver

- [ ] Vite + React + TypeScript prosjektskjelett
- [ ] Tailwind med XLENT-fargepalett (`xlent.config.ts`)
- [ ] Drag-and-drop filopplasting (react-dropzone)
- [ ] Debug-visning av parsede felter (rå JSON → tabell)
- [ ] Enkel invoice-liste med status
- [ ] API-klient med Axios/fetch + TanStack Query oppsett

### Definisjon av ferdig

En PDF kan lastes opp via frontend, parses på backend, og de ekstraherte feltene vises i en tabell.

---

## 4. Sprint 2 — LLM-ekstraksjon (uke 3–4)

**Mål:** LLM ekstraherer strukturerte felter fra invoices med konfidensscore.

### Backend-oppgaver

- [ ] LLM-abstraksjonslag:
  ```python
  # llm/base.py
  class LLMClient(ABC):
      async def extract_invoice(self, text: str) -> InvoiceExtraction: ...
      async def parse_agreement(self, text: str) -> AgreementStructure: ...

  # llm/claude.py
  class ClaudeClient(LLMClient): ...

  # llm/openai.py
  class OpenAIClient(LLMClient): ...
  ```
- [ ] Prompt-engineering for invoice-ekstraksjon:
  - System-prompt med compliance-kontekst
  - Few-shot eksempler (3-5 norske/engelske invoices)
  - Strukturert JSON-output med felter:
    ```json
    {
      "invoice_number": {"value": "INV-2024-1234", "confidence": 0.95},
      "seller": {"name": "...", "country": "...", "confidence": 0.92},
      "buyer": {"name": "...", "country": "...", "address": "...", "confidence": 0.88},
      "line_items": [
        {"description": "...", "quantity": 5, "unit_price": 1200, "confidence": 0.90}
      ],
      "total_amount": {"value": 6000, "currency": "NOK", "confidence": 0.97},
      "delivery_address": {"value": "...", "country": "...", "confidence": 0.85}
    }
    ```
- [ ] Konfidens-routing: felt med konfidens < 0.8 → flagges for manuell review
- [ ] Endepunkt: `POST /api/invoices/{id}/extract` — trigger LLM-ekstraksjon
- [ ] Lagre ekstraherte felter i databasen (koble til invoice)
- [ ] Enhetstester mot 15-20 reelle invoices, mål precision/recall per felt
- [ ] Kostnadstracking: logg token-forbruk og estimert kostnad per invoice

### Frontend-oppgaver

- [ ] Invoice-detaljvisning med ekstraherte felter
- [ ] Konfidens-indikatorer per felt (fargekode: grønn > 0.9, gul > 0.8, rød < 0.8)
- [ ] Inline-redigering for felt med lav konfidens
- [ ] Knapp: "Ekstraher på nytt" (re-run LLM)
- [ ] Visning av rå PDF ved siden av ekstraherte felter (side-by-side)

### Definisjon av ferdig

En invoice parses og LLM-en ekstraherer alle felter med konfidensscore. Brukeren kan se og korrigere felter. Precision > 90% på 15+ test-invoices.

---

## 5. Sprint 3 — Sanksjonsscreening (uke 5–6)

**Mål:** Alle entiteter i en invoice screenes automatisk mot sanksjonslister.

### Gratiskilder som lastes ned

| Kilde | Format | URL | Oppdatering |
|-------|--------|-----|-------------|
| UN Consolidated List | XML | `https://scsanctions.un.org/resources/xml/en/consolidated.xml` | Ved endring |
| EU Financial Sanctions | XML | `https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content` | Daglig |
| US OFAC SDN | CSV | `https://www.treasury.gov/ofac/downloads/sdn.csv` | Daglig |
| OFAC Consolidated | CSV | `https://www.treasury.gov/ofac/downloads/consolidated/cons_prim.csv` | Daglig |
| Norsk sanksjonsliste | Via DEKSA | `https://deksa.no` | Ad-hoc |

### Backend-oppgaver

- [ ] Sanksjonsdata-loader:
  - `sanctions/loaders/un.py` — parse UN XML
  - `sanctions/loaders/eu.py` — parse EU XML
  - `sanctions/loaders/ofac.py` — parse OFAC CSV
  - Felles `SanctionedEntity`-modell: navn, aliaser, land, type, kilde
  - Daglig cron-jobb: last ned, parse, oppdater database
  - Logg oppdateringer, varsle ved feil
- [ ] OpenSanctions yente (self-hosted):
  - Docker-kontainer med yente matching API
  - Konfigurer mot OpenSanctions-datasett (gratis for PoC)
  - Brukes for fuzzy matching, alias-matching, translitterasjon
- [ ] Screening-endepunkt: `POST /api/screen`
  ```json
  {
    "entities": [
      {"name": "Hidirusta Otomotiv", "type": "company", "country": "TR"},
      {"name": "Ivan Petrov", "type": "person", "country": "RU"}
    ]
  }
  ```
  Returnerer:
  ```json
  {
    "results": [
      {
        "entity": "Hidirusta Otomotiv",
        "matches": [
          {"list": "EU", "score": 0.85, "matched_name": "...", "sanctions_type": "asset_freeze"}
        ],
        "status": "flagged"
      }
    ]
  }
  ```
- [ ] Celery-task: ved ny invoice → screen alle entiteter automatisk
- [ ] Endepunkt: `GET /api/invoices/{id}/screening` — hent screeningresultat
- [ ] Endepunkt: `POST /api/sanctions/refresh` — manuell oppdatering av lister

### Frontend-oppgaver

- [ ] Trafikklys-badge per invoice i listen (grønt/gult/rødt)
- [ ] Screening-resultat i invoice-detaljvisning
- [ ] Drill-down: hvilke entiteter matchet, mot hvilken liste, med hvilken score
- [ ] Filtrering av invoice-listen på screening-status

### Definisjon av ferdig

**Demo-klar.** En invoice lastes opp → parses → screenes → viser trafikklys. Kan demonstreres for pilotkunder. Falsk-positive-rate < 10% på testdata.

---

## 6. Sprint 4 — Regelmotor og avtaler (uke 7–8)

**Mål:** Konfigurerbare regler og rammeavtale-matching.

### Backend-oppgaver

- [ ] Regelmotor:
  - Regelformat i YAML:
    ```yaml
    rules:
      - id: RULE-001
        name: "Restriktivt land — høyt beløp"
        description: "Flagg invoices til landgruppe C over 500 000 NOK"
        conditions:
          - field: buyer.country
            operator: in
            value: ["RU", "BY", "IR", "KP", "SY", "CU"]
          - field: total_amount.value
            operator: ">"
            value: 500000
        logic: AND
        action: red
        severity: critical
        requires_approval: "head_of_compliance"

      - id: RULE-002
        name: "Dual-use varekode"
        description: "Flagg produkter som starter med ML-prefix"
        conditions:
          - field: line_items.description
            operator: contains
            value: ["ML", "ECCN", "dual-use"]
        action: yellow
        severity: warning
    ```
  - Regelparser: last YAML, evaluer mot invoice-data
  - Støtte for AND/OR/NOT, regex, wildcards, beløpsgrenser
  - Versjonskontroll: alle endringer i `rule_versions`-tabell
  - Test-modus: evaluer regler mot historiske invoices uten å trigge varsler
- [ ] CRUD API for regler:
  - `GET /api/rules` — liste alle aktive regler
  - `POST /api/rules` — opprett ny regel
  - `PUT /api/rules/{id}` — oppdater regel (ny versjon)
  - `DELETE /api/rules/{id}` — deaktiver regel (soft delete)
  - `POST /api/rules/{id}/test` — kjør regel mot N historiske invoices
- [ ] Rammeavtale-modul:
  - `POST /api/agreements/upload` — last opp avtale-PDF
  - LLM-parsing til strukturert JSON:
    ```json
    {
      "agreement_id": "RA-2024-042",
      "customer": "Aker Solutions ASA",
      "valid_from": "2024-01-01",
      "valid_to": "2025-12-31",
      "allowed_products": ["subsea control systems", "umbilicals"],
      "allowed_countries": ["NO", "GB", "US", "BR"],
      "max_annual_volume": 50000000,
      "price_terms": { ... },
      "special_conditions": "..."
    }
    ```
  - Matching: sjekk invoice mot avtalebetingelser
  - Rapporter avvik: feil produkt, feil land, pris utenfor avtale, utløpt avtale
- [ ] Endepunkt: `GET /api/invoices/{id}/compliance` — samlet resultat fra alle sjekker

### Frontend-oppgaver

- [ ] Regel-editor med visuell builder (betingelse → operator → verdi)
- [ ] Regeloversikt: aktive/deaktiverte, versjon, siste kjøring
- [ ] Test-modus-visning: resultater av regelkjøring mot historikk
- [ ] Avtale-oversikt: liste, status, utløpsdato
- [ ] Avvik-visning per invoice: hva brøt mot avtalen

### Definisjon av ferdig

Minst 10 regler konfigurert og kjørt mot testdata. 3 rammeavtaler importert og matchet mot invoices. Avvik identifiseres korrekt.

---

## 7. Sprint 5 — Review-UI og audit (uke 9–10)

**Mål:** Controller-arbeidsflate for daglig compliance-arbeid.

### Backend-oppgaver

- [ ] Beslutningsmotor (`decision/engine.py`):
  - Aggreger resultater fra LLM-ekstraksjon, sanksjonsscreening, regelmotor, og avtalematch
  - Samlet compliance-score med vekting per kategori
  - Tre utfall: `approved` (grønt), `warning` (gult), `blocked` (rødt)
  - Strukturert begrunnelse for hvert utfall
- [ ] Audit-logg:
  - Append-only tabell: `audit_log`
  - Felter: `invoice_id`, `action`, `user_id`, `reason`, `timestamp`, `rule_version`, `previous_hash`
  - Hash-kjedet: hver rad inneholder hash av forrige rad (tamper-evident)
  - Ingen UPDATE eller DELETE på denne tabellen
- [ ] Case management:
  - `POST /api/cases/{id}/decision` — godkjenn, eskaler, eller blokker
  - Obligatorisk begrunnelse ved gult og rødt
  - Tilordning til spesifikk bruker
  - Kommentar-tråd per case
- [ ] RBAC:
  - `controller` — kan se og behandle egne saker
  - `compliance_officer` — kan se og behandle alle saker, endre regler
  - `admin` — full tilgang, brukeradministrasjon
  - `readonly` — kun lesetilgang (revisor)
- [ ] Rapport-generering:
  - `GET /api/reports/monthly?year=2026&month=5` — månedlig compliance-rapport
  - PDF-eksport med oppsummering, statistikk, liste over flaggede invoices
  - Kvartalsoversikt for styre/revisor

### Frontend-oppgaver — dette er den viktigste skjermen

- [ ] **Review-kø** (hovedvisning):
  - Sortert etter risiko (rødt først, deretter gult)
  - Filtrerbar: status, type flagg, land, beløpsintervall, dato
  - Kolonner: invoice-nr, kunde, land, beløp, status, flagg-type, tilordnet
  - Batch-operasjoner: godkjenn flere grønne samtidig
- [ ] **Saksvisning** (invoice-detalj):
  - Venstre: invoice-PDF (embedded viewer)
  - Høyre: ekstraherte data, sanksjonsresultat, regelresultat, avtaleavvik
  - Alt i ett bilde — controlleren skal ikke måtte klikke mellom faner
  - Handlingsknapper: Godkjenn / Eskaler / Blokker
  - Obligatorisk begrunnelsesfelt ved gult/rødt
  - Kommentar-tråd
- [ ] **Dashboard**:
  - Antall invoices behandlet (uke/mnd)
  - Åpne flagg per kategori
  - Gjennomsnittlig behandlingstid
  - Trend: flagg over tid (linjediagram)
  - Topp 5 kunder med flest flagg
- [ ] **Audit-trail** per invoice:
  - Tidslinje: hvem så hva, når, hvilken beslutning, hvilken begrunnelse
  - Ikke-redigerbar visning

### Definisjon av ferdig

En controller kan logge inn, se sin review-kø, åpne en sak, se all kontekst i ett bilde, og ta en beslutning med begrunnelse. Beslutningen logges i audit-loggen. Dashboard viser statistikk.

---

## 8. Sprint 6 — Integrasjon og hardening (uke 11–12)

**Mål:** Produksjonsklar MVP med reelle integrasjoner.

### Backend-oppgaver

- [ ] E-post-inntak:
  - IMAP-poller som overvåker en innboks for innkommende invoice-PDF-er
  - Automatisk prosessering: mottak → parsing → screening → kø
  - Konfigurerbar: hvilken e-postadresse, polling-frekvens
- [ ] ERP-integrasjon (webhook):
  - `POST /api/webhooks/erp` — motta invoice-data fra SAP/IFS/Visma
  - JSON-payload med invoice-felter (for bedrifter med digitale systemer)
  - API-nøkkel-autentisering per kunde
- [ ] GDPR:
  - Data-minimering: kun nødvendige felt lagres
  - Konfigurerbar lagringstid per datatype (default 7 år for regnskap)
  - Automatisk sletting av utløpte data (Celery periodic task)
  - Eksport av persondata: `GET /api/gdpr/export/{customer_id}`
- [ ] Sikkerhet:
  - Rate limiting på alle endepunkter (slowapi)
  - API-nøkkel-autentisering for webhook-endepunkter
  - OAuth 2.0 / OIDC for brukerautentisering
  - TLS via Nginx reverse proxy
  - Input-validering og sanitering
- [ ] Ytelse:
  - Asynkron pipeline: invoice-opplasting returnerer umiddelbart, prosessering i bakgrunn
  - Bulk-prosessering: 50+ invoices om gangen
  - Caching av sanksjons-lookups (Redis, TTL 1 time)
  - Database-indekser på søkebare felter
- [ ] Ende-til-ende-tester:
  - 50-100 reelle invoices gjennom hele pipelinen
  - Mål: tid per invoice, precision, recall, falsk-positive-rate
- [ ] Deploy:
  - `docker-compose.prod.yml` med produksjonsinnstillinger
  - Nginx-konfigurasjon med TLS
  - Backup-strategi for PostgreSQL
  - Monitoring: healthcheck-endepunkt + simple uptime-sjekk

### Frontend-oppgaver

- [ ] Innstillinger-side:
  - Konfigurasjon av sanksjonslister (aktiver/deaktiver per liste)
  - Oppdateringsfrekvens
  - E-postvarsler: hvem varsles ved rødt flagg
- [ ] Onboarding-wizard for nye kunder:
  - Steg 1: Last opp rammeavtaler
  - Steg 2: Konfigurer regler (fra maler eller fra scratch)
  - Steg 3: Test-kjøring mot historiske invoices
  - Steg 4: Aktiver produksjon
- [ ] Feilhåndtering og tomme tilstander i hele UI-et
- [ ] Responsive design (fungerer på laptop og stor skjerm)

### Definisjon av ferdig

En pilotkunde kan sende invoices via e-post eller API, de prosesseres automatisk, controlleren behandler flagg, og compliance officer kan trekke en månedlig rapport. Hele flyten fungerer uten manuell inngripen fra Xlent.

---

## 9. Datamodell

```sql
-- Kjerne
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    country TEXT,
    org_number TEXT,
    risk_level TEXT DEFAULT 'normal',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number TEXT,
    customer_id UUID REFERENCES customers(id),
    direction TEXT NOT NULL CHECK (direction IN ('incoming', 'outgoing')),
    pdf_path TEXT NOT NULL,
    raw_text TEXT,
    status TEXT DEFAULT 'uploaded' CHECK (status IN (
        'uploaded', 'parsing', 'parsed', 'extracting', 'extracted',
        'screening', 'screened', 'reviewed', 'approved', 'blocked'
    )),
    total_amount NUMERIC,
    currency TEXT,
    invoice_date DATE,
    compliance_score TEXT CHECK (compliance_score IN ('green', 'yellow', 'red')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE invoice_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    line_number INTEGER,
    description TEXT,
    product_code TEXT,
    quantity NUMERIC,
    unit_price NUMERIC,
    total_price NUMERIC
);

CREATE TABLE extracted_fields (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    field_value TEXT,
    confidence NUMERIC,
    manually_corrected BOOLEAN DEFAULT FALSE,
    corrected_value TEXT,
    corrected_by UUID,
    corrected_at TIMESTAMPTZ
);

-- Entiteter (for sanksjonsscreening)
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    entity_type TEXT CHECK (entity_type IN ('person', 'company', 'vessel', 'aircraft')),
    country TEXT,
    role TEXT CHECK (role IN ('seller', 'buyer', 'end_user', 'delivery_address', 'other'))
);

-- Sanksjonsscreening
CREATE TABLE screening_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    list_source TEXT NOT NULL,
    matched_name TEXT,
    match_score NUMERIC,
    sanctions_type TEXT,
    status TEXT CHECK (status IN ('clear', 'potential_match', 'confirmed_match')),
    screened_at TIMESTAMPTZ DEFAULT now()
);

-- Sanksjonslister (lokal kopi)
CREATE TABLE sanctions_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,
    last_updated TIMESTAMPTZ,
    entry_count INTEGER,
    update_status TEXT CHECK (update_status IN ('success', 'failed', 'updating'))
);

-- Regler
CREATE TABLE rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    conditions JSONB NOT NULL,
    logic TEXT DEFAULT 'AND',
    action TEXT CHECK (action IN ('green', 'yellow', 'red')),
    severity TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_by UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE rule_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id UUID REFERENCES rules(id),
    version INTEGER,
    conditions JSONB,
    changed_by UUID,
    changed_at TIMESTAMPTZ DEFAULT now(),
    change_reason TEXT
);

CREATE TABLE rule_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    rule_id UUID REFERENCES rules(id),
    rule_version INTEGER,
    triggered BOOLEAN,
    action TEXT,
    details TEXT,
    evaluated_at TIMESTAMPTZ DEFAULT now()
);

-- Rammeavtaler
CREATE TABLE agreements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id),
    agreement_number TEXT,
    pdf_path TEXT,
    valid_from DATE,
    valid_to DATE,
    structured_data JSONB,
    status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'expired')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE agreement_check_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    agreement_id UUID REFERENCES agreements(id),
    status TEXT CHECK (status IN ('within_agreement', 'deviation', 'no_agreement')),
    deviations JSONB,
    checked_at TIMESTAMPTZ DEFAULT now()
);

-- Beslutninger og audit
CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID REFERENCES invoices(id),
    decision TEXT CHECK (decision IN ('approved', 'escalated', 'blocked')),
    reason TEXT NOT NULL,
    decided_by UUID NOT NULL,
    decided_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID,
    action TEXT NOT NULL,
    user_id UUID,
    details JSONB,
    previous_hash TEXT,
    current_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
-- Ingen UPDATE eller DELETE tillatt på audit_log

-- Brukere
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    role TEXT CHECK (role IN ('controller', 'compliance_officer', 'admin', 'readonly')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 10. API-endepunkter

### Invoices

| Metode | Endepunkt | Beskrivelse | Sprint |
|--------|-----------|-------------|--------|
| POST | `/api/invoices/upload` | Last opp invoice-PDF | 1 |
| GET | `/api/invoices` | Liste med paginering og filter | 1 |
| GET | `/api/invoices/{id}` | Hent invoice med alle data | 1 |
| POST | `/api/invoices/{id}/extract` | Trigger LLM-ekstraksjon | 2 |
| PUT | `/api/invoices/{id}/fields/{field_id}` | Korriger ekstrahert felt | 2 |
| GET | `/api/invoices/{id}/screening` | Hent screeningresultat | 3 |
| GET | `/api/invoices/{id}/rules` | Hent regelresultater | 4 |
| GET | `/api/invoices/{id}/agreement` | Hent avtalematch-resultat | 4 |
| GET | `/api/invoices/{id}/compliance` | Samlet compliance-resultat | 5 |
| GET | `/api/invoices/{id}/audit` | Audit-trail for invoice | 5 |

### Screening

| Metode | Endepunkt | Beskrivelse | Sprint |
|--------|-----------|-------------|--------|
| POST | `/api/screen` | Screen entiteter mot lister | 3 |
| POST | `/api/sanctions/refresh` | Oppdater sanksjonslister | 3 |
| GET | `/api/sanctions/status` | Status for alle lister | 3 |

### Regler

| Metode | Endepunkt | Beskrivelse | Sprint |
|--------|-----------|-------------|--------|
| GET | `/api/rules` | Liste alle regler | 4 |
| POST | `/api/rules` | Opprett ny regel | 4 |
| PUT | `/api/rules/{id}` | Oppdater regel | 4 |
| DELETE | `/api/rules/{id}` | Deaktiver regel | 4 |
| POST | `/api/rules/{id}/test` | Test-kjør mot historiske invoices | 4 |

### Avtaler

| Metode | Endepunkt | Beskrivelse | Sprint |
|--------|-----------|-------------|--------|
| POST | `/api/agreements/upload` | Last opp rammeavtale-PDF | 4 |
| GET | `/api/agreements` | Liste alle avtaler | 4 |
| GET | `/api/agreements/{id}` | Hent avtale med strukturerte data | 4 |

### Cases og beslutninger

| Metode | Endepunkt | Beskrivelse | Sprint |
|--------|-----------|-------------|--------|
| GET | `/api/cases` | Review-kø med filtrering | 5 |
| POST | `/api/cases/{id}/decision` | Registrer beslutning | 5 |
| POST | `/api/cases/{id}/comment` | Legg til kommentar | 5 |
| POST | `/api/cases/{id}/assign` | Tilordne til bruker | 5 |

### Rapporter

| Metode | Endepunkt | Beskrivelse | Sprint |
|--------|-----------|-------------|--------|
| GET | `/api/reports/monthly` | Månedlig compliance-rapport | 5 |
| GET | `/api/reports/dashboard` | Dashboard-data | 5 |

### Administrasjon

| Metode | Endepunkt | Beskrivelse | Sprint |
|--------|-----------|-------------|--------|
| GET | `/api/health` | Helsesjekk | 1 |
| POST | `/api/webhooks/erp` | ERP-webhook for invoices | 6 |
| GET | `/api/gdpr/export/{customer_id}` | GDPR-eksport | 6 |

---

## 11. Prosjektstruktur

```
xlent-compliance/
├── docker-compose.yml
├── docker-compose.prod.yml
├── README.md
├── .github/
│   └── workflows/
│       ├── test.yml
│       └── deploy.yml
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   │   ├── alembic.ini
│   │   └── versions/
│   ├── app/
│   │   ├── main.py                    # FastAPI app, CORS, middleware
│   │   ├── config.py                  # Pydantic Settings
│   │   ├── database.py                # SQLAlchemy async engine
│   │   ├── models/                    # SQLAlchemy modeller
│   │   │   ├── invoice.py
│   │   │   ├── entity.py
│   │   │   ├── screening.py
│   │   │   ├── rule.py
│   │   │   ├── agreement.py
│   │   │   ├── decision.py
│   │   │   ├── audit.py
│   │   │   └── user.py
│   │   ├── schemas/                   # Pydantic schemas (request/response)
│   │   │   ├── invoice.py
│   │   │   ├── screening.py
│   │   │   ├── rule.py
│   │   │   └── ...
│   │   ├── api/                       # Endepunkter
│   │   │   ├── invoices.py
│   │   │   ├── screening.py
│   │   │   ├── rules.py
│   │   │   ├── agreements.py
│   │   │   ├── cases.py
│   │   │   ├── reports.py
│   │   │   └── webhooks.py
│   │   ├── parsers/                   # PDF-parsing
│   │   │   ├── pdf_parser.py          # pdfplumber
│   │   │   ├── ocr_parser.py          # Tesseract
│   │   │   └── router.py             # Autodeteksjon: digital vs skannet
│   │   ├── llm/                       # LLM-abstraksjon
│   │   │   ├── base.py               # ABC
│   │   │   ├── claude.py
│   │   │   ├── openai.py
│   │   │   ├── prompts/
│   │   │   │   ├── invoice_extraction.py
│   │   │   │   └── agreement_parsing.py
│   │   │   └── output_parser.py
│   │   ├── sanctions/                 # Sanksjonsscreening
│   │   │   ├── loaders/
│   │   │   │   ├── un.py
│   │   │   │   ├── eu.py
│   │   │   │   └── ofac.py
│   │   │   ├── matcher.py            # Fuzzy matching
│   │   │   └── scheduler.py          # Daglig oppdatering
│   │   ├── rules/                     # Regelmotor
│   │   │   ├── engine.py
│   │   │   ├── parser.py             # YAML → evaluering
│   │   │   └── default_rules/
│   │   │       └── sanctions_basic.yaml
│   │   ├── decision/                  # Beslutningsmotor
│   │   │   └── engine.py
│   │   ├── audit/                     # Audit-logg
│   │   │   └── logger.py             # Hash-kjedet logging
│   │   └── tasks/                     # Celery-tasks
│   │       ├── celery_app.py
│   │       ├── process_invoice.py
│   │       ├── screen_entities.py
│   │       └── update_sanctions.py
│   └── tests/
│       ├── conftest.py
│       ├── fixtures/                  # Test-invoices (PDF)
│       ├── test_parsers.py
│       ├── test_llm_extraction.py
│       ├── test_screening.py
│       ├── test_rules.py
│       └── test_api.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts             # XLENT-farger
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/                       # API-klient
│   │   │   └── client.ts
│   │   ├── hooks/                     # TanStack Query hooks
│   │   │   ├── useInvoices.ts
│   │   │   ├── useScreening.ts
│   │   │   └── useRules.ts
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── InvoiceList.tsx
│   │   │   ├── InvoiceDetail.tsx
│   │   │   ├── ReviewQueue.tsx
│   │   │   ├── RuleEditor.tsx
│   │   │   ├── Agreements.tsx
│   │   │   ├── Reports.tsx
│   │   │   └── Settings.tsx
│   │   ├── components/
│   │   │   ├── InvoiceUploader.tsx
│   │   │   ├── TrafficLight.tsx
│   │   │   ├── ConfidenceBadge.tsx
│   │   │   ├── AuditTimeline.tsx
│   │   │   ├── ComplianceScore.tsx
│   │   │   └── ...
│   │   └── lib/
│   │       └── utils.ts
│   └── public/
│
└── docs/
    ├── architecture.md
    ├── api-reference.md
    └── deployment.md
```

---

## 12. Hva som bevisst er utelatt fra MVP

Følgende er fase 2+ funksjonalitet og skal **ikke** bygges i MVP:

| Funksjonalitet | Grunn til utelatelse | Fase |
|----------------|---------------------|------|
| Kunnskapsgraf (Neo4j/AGE) | Krever nok data over tid for å gi verdi | 2 |
| Graf-basert anomali-deteksjon | Avhenger av kunnskapsgrafen | 2 |
| RAG-pipeline med vektordatabase | Overkill for MVP, direkte oppslag holder | 2 |
| On-prem LLM (Llama/Mistral) | Bare relevant når en kunde krever det | 2 |
| Læringsløkker (review → regler) | Krever nok review-data | 3 |
| Eksportkontroll-klassifisering (ECCN) | Kompleks, trenger domeneekspert | 2 |
| Sluttbruker-analyse / eierskap | Krever tilleggsdata (register, Orbis) | 2 |
| Adverse media screening | Kan legges til via ComplyAdvantage API | 2 |
| Multi-tenant arkitektur | Én kunde per instans i MVP | 3 |
| Avanserte dashboards / BI | Enkel statistikk holder i MVP | 2 |

---

## 13. Etter MVP — fase 2

Når MVP er i produksjon hos første pilotkunde, er dette prioriteringslisten:

1. **Kunnskapsgraf** — Apache AGE (PostgreSQL-utvidelse) for å unngå ny databasemotor. Begynn å akkumulere entiteter og relasjoner.
2. **RAG-pipeline** — Vektordatabase (Pinecone eller Weaviate) for semantisk søk i sanksjonslister og avtaletekster. Gir bedre fuzzy matching.
3. **On-prem LLM** — Llama 3 / Mistral via vLLM for kunder som ikke kan sende data til sky.
4. **Graf-anomali** — Når grafen har 3-6 måneder med data: mønstergjenkjenning på adresser, eierskap, frekvens.
5. **Læringsløkker** — Bruk controller-begrunnelser til å justere regler og terskler automatisk.
6. **Multi-tenant** — Når kunde nr. 2 og 3 kommer: felles plattform med isolert data.

---

*Dokumentet er et internt arbeidsutkast fra Xlent og skal brukes som grunnlag for prosjektplanlegging og ressursallokering.*
