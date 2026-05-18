# Risikoregister — XLENT Compliance

Dette registeret dokumenterer kjente risikoer ved AI-komponentene i systemet og hvilke tiltak som reduserer dem. Vedlikeholdes i henhold til EU AI Act Art. 9 (risikostyringssystem).

Oppdateres ved vesentlige endringer i AI-komponentene eller når nye risikoer identifiseres.

## Risikoklassifisering

| ID | Risiko | Sannsynlighet | Konsekvens | Tiltak | Status |
|----|--------|---------------|------------|--------|--------|
| R-001 | **Hallusinering i LLM-ekstraksjon** — modellen finner opp felter eller verdier som ikke står i invoicen | Middels | Høy | Konfidensscore per felt; alt under 0.8 eskaleres til manuell review. LLM-output valideres mot Pydantic-skjema. | Aktiv (sprint 2) |
| R-002 | **Falske negativer i sanksjonsscreening** — sanksjonert entitet blir ikke flagget pga. translitterasjon, alias eller stavefeil | Middels | Kritisk | OpenSanctions yente med fuzzy matching; daglig oppdatering av lister; manuell override-mulighet; alle screening-resultater logges. | Aktiv (sprint 3) |
| R-003 | **Falske positiver i sanksjonsscreening** — gyldige transaksjoner blir feilaktig blokkert | Høy | Middels | Konfigurerbar match-terskel; controllers kan overprøve med begrunnelse; alle false positives logges for tuning. | Aktiv (sprint 3) |
| R-004 | **Bias i LLM-ekstraksjon** — modellen håndterer ikke-engelske invoices eller spesifikke språk dårligere | Middels | Middels | Test-set med norske, engelske, tyske og russiske invoices; precision/recall-måling per språk i CI; manuell review-fallback. | Planlagt (sprint 2) |
| R-005 | **Adversarial input** — manipulert invoice (skjult tekst, misvisende OCR) designet for å omgå screening | Lav | Høy | OCR-output og digitalt parset tekst sammenlignes; mistenkelige avvik flagges; rå PDF lagres for revisor. | Planlagt (sprint 6) |
| R-006 | **LLM-leverandør utilgjengelig** — Anthropic/OpenAI nede eller rate-limited | Lav | Middels | Abstraksjonslag med automatisk fallback til alternativ leverandør; retry-logikk; status synlig i dashboard. | Aktiv (sprint 2) |
| R-007 | **Audit-logg tampering** — beslutninger endres etter at de er gjort | Lav | Kritisk | Append-only tabell; hash-kjedet; ingen UPDATE/DELETE-rettigheter for app-bruker; periodisk hash-verifisering. | Planlagt (sprint 5) |
| R-008 | **Persondata-lekkasje til LLM-leverandør** — sensitive felter sendes til sky-LLM uten samtykke | Lav | Høy | Databehandleravtaler (DPA) med Anthropic/OpenAI; opt-out av treningsdata; on-prem LLM-alternativ planlagt (fase 2). | Planlagt (sprint 6) |
| R-009 | **Foreldede sanksjonslister** — listene blir ikke oppdatert og systemet jobber mot utdatert data | Lav | Kritisk | Daglig cron-job; varsel hvis oppdatering feiler > 24 t; screening avvises hvis liste er > 48 t gammel. | Planlagt (sprint 3) |
| R-010 | **Regel-feil med stor konsekvens** — feil i ny regel auto-godkjenner flagg som burde stoppes | Middels | Høy | Test-modus mot historiske invoices før aktivering; regelversjonering; rollback-mulighet. | Planlagt (sprint 4) |

## Vurderingsskala

**Sannsynlighet:** Lav (< 5 % per år), Middels (5–25 %), Høy (> 25 %).
**Konsekvens:** Lav (mindre operasjonell ulempe), Middels (signifikant gjenoppretting kreves), Høy (regulatorisk eller omdømmeskade), Kritisk (lovbrudd, bøter, eller blokkert virksomhet).
