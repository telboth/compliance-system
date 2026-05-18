# API-referanse

Autoritativ, levende API-dokumentasjon genereres av FastAPI på <http://localhost:8000/docs> (Swagger UI) og <http://localhost:8000/redoc> (ReDoc).

Denne filen samler designnotater som ikke fanges av OpenAPI-spesifikasjonen.

## Konvensjoner

- Alle endepunkter er prefikset `/api/v1`.
- Tidsstempler bruker ISO 8601 i UTC.
- UUID-er for primærnøkler.
- Paginering: query-parametre `?limit=50&offset=0`. Maks `limit` er 200.
- Filtrering: query-parametre med samme navn som modellfelt (`?status=red&country=NO`).
- Sortering: `?sort=-created_at` (prefix `-` for synkende).

## Feilrespons

```json
{
  "detail": "Beskrivelse av feilen",
  "code": "INVOICE_NOT_FOUND",
  "field_errors": [
    {"field": "invoice_number", "error": "Påkrevd"}
  ]
}
```

## Autentisering

Sprint 6: JWT via `Authorization: Bearer <token>`. Endepunkter for webhook bruker API-nøkkel via `X-API-Key`-header.

## Endepunkter per sprint

Se `docs/MVP_Byggeplan.md` for fullstendig oversikt over hvilke endepunkter som leveres når.
