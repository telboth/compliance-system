# Test-fixturer

## Statiske fixturer

Minimale syntetiske filer brukt av enhetstester (ingen ML-modeller):

| Fil | Brukt av |
|-----|----------|
| `conftest.py::sample_pdf_bytes` | Upload- og parser-enhetstester |
| `conftest.py::sample_xlsx_bytes` | XLSX-parser-enhetstester |

## Fasit-filer for integrasjonstester (`expected/`)

Katalogen `expected/` inneholder YAML-fasit-filer for faktura-filene i
`Test_invoices/` (prosjektrot). Én fil per faktura, navngitt etter
filnavnet uten filtype.

### Format

```yaml
invoice_number: "INV-2024-001"   # eksakt match (case-insensitive)
invoice_date: "2024-03-15"       # YYYY-MM-DD
total_amount: "12345.00"         # numerisk, ±0.01 toleranse
currency: "USD"                  # ISO 4217
incoterms: "CIF"
transport_mode: "sea"
destination_country: "NO"        # ISO 3166-1 alpha-2
po_number: null                  # null = hoppes over i sammenligning

entities:
  - name: "ACME Corp"
    role: "seller"               # seller|buyer|consignor|consignee|end_user
  - name: null                   # kun rolle sjekkes
    role: "buyer"

lines:
  - hs_code: "8471.30"
    eccn: "5A002"
    country_of_origin: "US"
    currency: "USD"
```

### Legg til ny faktura

1. Legg faktura-filen i `Test_invoices/` (støtter `.pdf`, `.png`, `.jpg`, `.xlsx`)
2. Generer initial fasit automatisk:
   ```bash
   cd backend/
   python scripts/generate_ground_truth.py
   ```
3. Korriger de auto-genererte verdiene manuelt mot originaldokumentet.
4. Kjør testene for å verifisere:
   ```bash
   pytest tests/test_real_invoices.py -m slow -v -s
   ```

### Sikkerhet

**PDF-er og bilder som inneholder persondata skal IKKE committes til repoet.**
Bruk anonymiserte versjoner eller hold dem utenfor git via `.gitignore`.

Faktura-filene i `Test_invoices/` er lagt til i `.gitignore` av samme grunn.
YAML-fasit-filene i `expected/` kan committes (de inneholder ingen persondata
— kun strukturerte felt-verdier).
