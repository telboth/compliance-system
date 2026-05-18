# GDPR-behandlingsoversikt — XLENT Compliance

Denne dokumentasjonen utfyller `SKILL.md`-seksjonen om GDPR. Den brukes som grunnlag for protokoll over behandlingsaktiviteter (Art. 30) hos kunden.

## Behandlingsaktiviteter

| Aktivitet | Personopplysninger | Behandlingsgrunnlag | Lagringstid |
|-----------|--------------------|--------------------|-------------|
| Invoice-mottak og parsing | Navn, adresser, kontaktpersoner i invoice | Berettiget interesse (Art. 6(1)(f)) — compliance-kontroll | 7 år (regnskapsloven) |
| Sanksjonsscreening | Navn, adresser, fødselsdato (hvor relevant) | Rettslig forpliktelse (Art. 6(1)(c)) — sanksjonsregelverk | 7 år |
| LLM-prosessering | Strukturert utdrag av invoice-tekst | Berettiget interesse | Slettes etter prosessering (rå output) |
| Audit-logg | Bruker-ID, handling, tidsstempel | Rettslig forpliktelse — revisjonsspor | 10 år |
| Brukerkontoer | E-post, navn, rolle | Avtale (Art. 6(1)(b)) — tilgang til systemet | Inntil sletting av konto |

## Databehandlere

| Leverandør | Tjeneste | Persondata behandlet | DPA-status |
|------------|----------|----------------------|------------|
| Anthropic | Claude LLM | Strukturert invoice-tekst | Må inngås før produksjon |
| OpenAI | GPT-4o (backup) | Strukturert invoice-tekst | Må inngås før produksjon |
| OpenSanctions | yente (self-hosted) | Ingen — kjører lokalt | N/A |
| Hosting (Azure/AWS) | VM/lagring | All data | Standard cloud-DPA |

## Rettigheter

| Rettighet | Endepunkt | Implementert |
|-----------|-----------|--------------|
| Innsyn | `GET /api/v1/gdpr/export/{entity_id}` | Sprint 6 |
| Sletting | `DELETE /api/v1/gdpr/erase/{entity_id}` (beholder anonymisert audit-logg) | Sprint 6 |
| Retting | `PUT /api/v1/invoices/{id}/fields/{field_id}` | Sprint 2 |
| Begrensning | Manuell via admin-grensesnitt | Sprint 5 |

## Tekniske og organisatoriske tiltak (Art. 32)

- TLS 1.3 for all API-trafikk
- AES-256 for kryptering i ro (PDF-er og sensitive databasefelter)
- Krypteringsnøkler i miljøvariabler / secret manager — aldri i kode eller config-filer
- Tilgangskontroll: RBAC, MFA for admin-roller
- Audit-logging av alle tilganger til persondata
- Daglige Postgres-backups med 30-dagers oppbevaring
- Periodisk gjennomgang av tilgangsrettigheter
