# Arkitektur — XLENT Compliance

Detaljert arkitekturdokumentasjon. Komplementerer `docs/MVP_Byggeplan.md` (sprintplan og datamodell) og `SKILL.md` (forretningskontekst og prinsipper).

## Overordnet dataflyt

```
PDF inn → Parsing → LLM-ekstraksjon → Screening + Regler + Avtale-match
                                           ↓
                                    Beslutningsmotor
                                           ↓
                          Review (controller) → Audit-logg
```

## Komponenter

### Backend (FastAPI)

- `app/main.py` — FastAPI-applikasjon, CORS, middleware-registrering, router-mounting.
- `app/core/config.py` — Pydantic Settings, lest fra miljøvariabler.
- `app/core/database.py` — SQLAlchemy 2.0 async engine, session-factory.
- `app/core/logging.py` — structlog-konfigurasjon.
- `app/models/` — SQLAlchemy-modeller, én fil per domene-entitet.
- `app/schemas/` — Pydantic v2 request/response-modeller.
- `app/api/v1/` — Routere per ressurs (invoices, screening, rules, …).
- `app/parsers/` — PDF-parsing med autodeteksjon.
- `app/llm/` — LLM-abstraksjon (ABC + Anthropic + OpenAI-implementasjoner).
- `app/sanctions/` — Lasting og matching av sanksjonslister.
- `app/rules/` — Regelmotor (YAML → evaluering).
- `app/decision/` — Beslutningsmotor som aggregerer alle resultater.
- `app/audit/` — Hash-kjedet append-only logging.
- `app/tasks/` — Celery-tasks for asynkron prosessering.

### Frontend (React + Vite)

- `src/api/` — Typesikre API-klienter.
- `src/hooks/` — TanStack Query hooks per ressurs.
- `src/pages/` — Toppnivå-views (Dashboard, ReviewQueue, InvoiceDetail, …).
- `src/components/` — Gjenbrukbare UI-komponenter.

### Asynkron prosessering

Når en invoice lastes opp:

1. API-et lagrer PDF-en og oppretter en `invoices`-rad med status `uploaded`.
2. En Celery-task `process_invoice` plukker opp jobben:
   - Parser PDF → tekst
   - Kaller LLM for ekstraksjon
   - Screener entiteter
   - Evaluerer regler
   - Sjekker mot rammeavtaler
   - Aggregerer i beslutningsmotoren
3. Frontend poller status (eller bruker WebSocket i fase 2).

## Sikkerhet

- Alle endepunkter bak JWT-autentisering (fastapi-users).
- RBAC: `controller`, `compliance_officer`, `admin`, `readonly`.
- TLS terminert i Nginx i produksjon.
- Rate limiting via slowapi.
- Sensitive felter krypteres ved lagring (fase 6+).

## Skalering

MVP kjører på én maskin (én kunde per instans). Skalering kommer i fase 3 med multi-tenant.
