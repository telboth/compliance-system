# Arkitektur — XLENT Compliance

Detaljert arkitekturdokumentasjon. Komplementerer `docs/MVP_Byggeplan.md` (sprintplan og datamodell) og `SKILL.md` (forretningskontekst og prinsipper).

## Overordnet dataflyt

```
PDF inn → Parsing → LLM-ekstraksjon → Screening + Regler + Avtale-match
                                           ↓
                           Review- og statuslogikk i services
                                           ↓
                          Review (controller) → Audit-logg
```

## Komponenter

### Backend (FastAPI)

- `app/main.py` - oppstart, lifespan, CORS og router-mounting.
- `app/core/` - config, database, logging, errors og enkel rollevalidering.
- `app/api/v1/` - HTTP-ruter per ressurs.
- `app/models/` - SQLAlchemy-modeller.
- `app/schemas/` - Pydantic request/response-modeller.
- `app/parsers/` - Docling-basert parsing med autodeteksjon.
- `app/llm/` - LLM-klienter, prompts, response-parsing og heuristikk/merge.
- `app/sanctions/` - embargo-hjelpere, yente-klient og seed-/cachelogikk.
- `app/services/` - invoice-pipeline, screening, regler, avtaler, review, audit, risikokvantifisering, eksportkontroll, catch-all, varsler og dashboard/KRI.
- `app/tasks/` - Celery-tasks og async runtime-hjelpere.
- `app/rules/default_rules/` - plassholder for standardregler; ingen YAML-filer er sjekket inn ennå.

I dagens kode finnes det ikke egne `app/decision/`- eller `app/audit/`-pakker. Beslutnings- og auditlogikk ligger i services-laget og på `Invoice`-modellen.

### Frontend (React + Vite)

- `src/api/` - API-klienter og types.
- `src/hooks/` - TanStack Query hooks per ressurs.
- `src/pages/` - toppnivå-views som Dashboard, ReviewQueue og InvoiceDetail.
- `src/components/` - gjenbrukbare UI-komponenter.

### Asynkron prosessering

Når en invoice lastes opp:

1. `POST /api/v1/invoices/upload` lagrer filen og oppretter en `invoices`-rad med status `uploaded`.
2. API-et forsøker å legge jobben i Celery via `app.tasks.process_invoice.run`.
3. Hvis Celery-enqueue feiler, faller den tilbake til `BackgroundTasks`.
4. `process_invoice` kaller `invoice_service.parse_invoice_in_background`, som igjen går videre til parsing, ekstraksjon og videre pipeline-steg.
5. `extraction_service` kan trigge screening automatisk etter ekstraksjon når `AUTO_SCREEN_AFTER_EXTRACT=true`.
6. Frontend poller status og bruker `approval_state` fra API-et.

`Invoice.approval_state` beregnes automatisk fra `status` og `compliance_score` via SQLAlchemy-events på modellen.

## Sikkerhet

- Dagens rollevalidering er server-side og header-basert via `X-Actor-Role` og `X-Actor-Name`.
- `require_roles(...)` brukes på mange muterende ruter, men ikke alle ruter er låst ennå.
- JWT/fastapi-users er planlagt senere, ikke implementert i dagens kode.
- `GET /health` og `GET /config/keys/status` er åpne.

## Skalering

MVP kjører på én maskin (én kunde per instans). Skalering kommer i fase 3 med multi-tenant.
