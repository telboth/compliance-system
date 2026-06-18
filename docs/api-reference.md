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

Dagens kode bruker server-side rollevalidering via `X-Actor-Role` og `X-Actor-Name`.

- Gyldige roller: `admin`, `c_level`, `compliance_officer`, `controller`, `readonly`.
- Mange muterende ruter bruker `require_roles(...)`, men ikke alle ruter er låst ennå.
- `GET /api/v1/health` og `GET /api/v1/config/keys/status` er åpne.
- JWT via `Authorization: Bearer <token>` er planlagt senere, ikke implementert i denne checkouten.
- API-nøkkelbasert webhook-auth er også planlagt senere.
- `rules`- og `agreements`-rutene er fortsatt uten eksplisitt `require_roles(...)` i dagens kode.

## Endepunkter per sprint

Se `docs/MVP_Byggeplan.md` for fullstendig oversikt over hvilke endepunkter som leveres når.
