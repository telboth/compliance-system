# Teknisk dokumentasjon — XLENT Compliance

Denne dokumentasjonen oppfyller kravene i EU AI Act Art. 11 om teknisk dokumentasjon for AI-systemer. Den beskriver systemet på et nivå som lar en tredjepart (revisor, tilsynsmyndighet) forstå hvordan systemet fungerer, hvilke data det bruker og hvordan beslutninger tas.

## 1. Systembeskrivelse

XLENT Compliance er et AI-drevet system for compliance-kontroll av eksporttransaksjoner. Systemet:

- Mottar invoices (faktura-PDF-er) via opplasting
- Ekstraherer strukturerte felter fra invoicen ved hjelp av PDF-parsing (pdfplumber/Tesseract) og en stor språkmodell (LLM)
- Screener entiteter (kjøper, selger, sluttbruker) mot internasjonale sanksjonslister (UN, EU, OFAC, norske lister)
- Evaluerer transaksjonen mot konfigurerbare forretningsregler (YAML) og rammeavtaler
- Foreslår et utfall: godkjent (grønn), advarsel (gul), eller blokker (rød)
- Eskalerer gult og rødt til en menneskelig controller som tar endelig beslutning
- Logger alle beslutninger i en append-only, hash-kjedet audit-logg

## 2. Tiltenkt formål

Systemet er ment for compliance-controllere og compliance officers i norske eksportbedrifter. Det erstatter ikke menneskelig vurdering — det forhåndsbehandler invoices slik at controlleren kan fokusere på flagg som faktisk krever oppmerksomhet.

## 3. Komponenter og dataflyt

Se `docs/architecture.md` for diagram. Hovedkomponenter:

1. **Dokument-AI:** PDF → tekst/bilder via parser-autodeteksjon → LLM-ekstraksjon → strukturert JSON med konfidens per felt.
2. **Sanksjonsscreening:** `app/services/screening_service.py` håndterer yente-match, embargo, interne watchlister, eksportkontroll og catch-all-signaler.
3. **Regelmotor og avtaler:** `app/services/rule_engine_service.py` evaluerer YAML-regler, og `app/services/agreement_service.py` matcher invoices mot rammeavtaler.
4. **Review og status:** `app/services/invoice_review_service.py` håndterer menneskelig review, mens `Invoice.approval_state` beregnes fra status og compliance score.
5. **Audit-logg:** `app/services/audit_service.py` skriver hash-kjedede audit-innslag.

## 4. Datakilder

| Datatype | Kilde | Oppdateringsfrekvens |
|----------|-------|----------------------|
| Invoices | Kundens egne PDF-er | Per transaksjon |
| Eksterne screeningkilder | UK Sanctions: daglig via offentlig CSV; World Bank Debarred Firms and Individuals: månedlig via offentlig side | Daglig for UK / månedlig for World Bank |
| Sanksjonslister | UN, EU, OFAC, norske lister via OpenSanctions | Daglig |
| Rammeavtaler | Kundens egne PDF-er | Ved nye avtaler |
| Regler | Konfigurert av kunden | Ved behov |

## 5. AI-modeller

| Komponent | Modell | Leverandør | Versjon |
|-----------|--------|------------|---------|
| Invoice-ekstraksjon (primær) | Claude Sonnet 4 | Anthropic | claude-sonnet-4-20250514 |
| Invoice-ekstraksjon (backup) | GPT-4o | OpenAI | gpt-4o |
| Avtale-parsing | Claude Sonnet 4 | Anthropic | claude-sonnet-4-20250514 |

LLM-kall logges strukturert med modell, tokenbruk og statushendelser. I tillegg lagres AI-governance-rader per invoice i `ai_decision_records` med modell, provider, konfidens og rå metadata.

## 6. Menneskelig tilsyn (EU AI Act Art. 14)

- Systemet blokkerer aldri en transaksjon uten at en compliance officer kan oppheve blokkeringen.
- Gult og rødt flagg krever obligatorisk menneskelig review med begrunnelse.
- Grønne flagg kan auto-godkjennes, men er alltid overprøvbare.
- Alle override-handlinger logges i audit-loggen.

## 7. Nøyaktighet og robusthet (Art. 15)

- Precision, recall og falsk-positive-rate måles på et fastlagt testsett som del av CI/CD.
- Mål: precision > 90 %, falsk-positive-rate < 10 % på MVP-testsettet.
- Fallback-mekanismer ved LLM-feil: primær → backup → manuell ekstraksjon.

## 8. Datakvalitetskontroll (Art. 10)

- Hver sanksjonsliste-loader validerer innholdet etter nedlasting (forventet entry count, struktur, oppdateringsdato).
- Staleness-grenser er konfigurerbare per kilde; UK Sanctions og World Bank Debarred følger egne terskler.
- Treningsdata: ingen — systemet bruker pre-trente modeller. Few-shot eksempler i prompts dokumenteres i `backend/app/llm/prompts/`.

## 9. Begrensninger

- Systemet er optimalisert for norske og engelske invoices. Andre språk kan ha lavere precision.
- Skjønnsmessige beslutninger (om en konkret transaksjon faktisk bryter med en spesifikk paragraf) tas alltid av et menneske.
- Systemet erstatter ikke juridisk rådgivning.

## 10. Versjonering

Endringer i AI-komponentene dokumenteres i `CHANGELOG.md` med dato, ansvarlig og rasjonale. Modellversjoner låses i konfigurasjon (`backend/app/core/config.py`).
