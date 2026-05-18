# Teknisk dokumentasjon — XLENT Compliance

Denne dokumentasjonen oppfyller kravene i EU AI Act Art. 11 om teknisk dokumentasjon for AI-systemer. Den beskriver systemet på et nivå som lar en tredjepart (revisor, tilsynsmyndighet) forstå hvordan systemet fungerer, hvilke data det bruker og hvordan beslutninger tas.

## 1. Systembeskrivelse

XLENT Compliance er et AI-drevet system for compliance-kontroll av eksporttransaksjoner. Systemet:

- Mottar invoices (faktura-PDF-er) via opplasting, e-post eller API
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

1. **Dokument-AI:** PDF → tekst (pdfplumber for digitalt, Tesseract for skannet) → LLM-ekstraksjon → strukturert JSON med konfidens per felt.
2. **Sanksjonsscreening:** OpenSanctions yente (self-hosted, MIT) med fuzzy matching mot konsoliderte lister.
3. **Regelmotor:** YAML-konfigurerte regler med AND/OR/NOT-logikk, versjonert.
4. **Avtale-matching:** LLM parser rammeavtaler til JSON; invoices sjekkes mot avtalebetingelser.
5. **Beslutningsmotor:** Aggregerer alle resultater til samlet score.
6. **Audit-logg:** Append-only, hash-kjedet, hellig.

## 4. Datakilder

| Datatype | Kilde | Oppdateringsfrekvens |
|----------|-------|----------------------|
| Invoices | Kundens egne PDF-er | Per transaksjon |
| Sanksjonslister | UN, EU, OFAC, norske lister via OpenSanctions | Daglig |
| Rammeavtaler | Kundens egne PDF-er | Ved nye avtaler |
| Regler | Konfigurert av kunden | Ved behov |

## 5. AI-modeller

| Komponent | Modell | Leverandør | Versjon |
|-----------|--------|------------|---------|
| Invoice-ekstraksjon (primær) | Claude Sonnet 4 | Anthropic | claude-sonnet-4-20250514 |
| Invoice-ekstraksjon (backup) | GPT-4o | OpenAI | gpt-4o |
| Avtale-parsing | Claude Sonnet 4 | Anthropic | claude-sonnet-4-20250514 |

Alle LLM-kall logges med input, output, modellversjon og tidsstempel.

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
- Lister som er > 48 timer gamle avvises automatisk.
- Treningsdata: ingen — systemet bruker pre-trente modeller. Few-shot eksempler i prompts dokumenteres i `backend/app/llm/prompts/`.

## 9. Begrensninger

- Systemet er optimalisert for norske og engelske invoices. Andre språk kan ha lavere precision.
- Skjønnsmessige beslutninger (om en konkret transaksjon faktisk bryter med en spesifikk paragraf) tas alltid av et menneske.
- Systemet erstatter ikke juridisk rådgivning.

## 10. Versjonering

Endringer i AI-komponentene dokumenteres i `CHANGELOG.md` med dato, ansvarlig og rasjonale. Modellversjoner låses i konfigurasjon (`app/config.py`).
