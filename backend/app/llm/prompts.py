"""
Prompts for invoice field extraction.

System-prompten er på engelsk for å gi LLM-en best mulig kontekst
(opplæringsdata for faglig engelsk er vesentlig bedre enn norsk).
Invoicene selv er på varierende språk — LLM-en håndterer det automatisk.
"""

from __future__ import annotations

from pathlib import Path

INVOICE_EXTRACTION_SYSTEM = """\
You are an expert compliance document analyst specializing in export control and trade compliance.
Your task is to extract structured data from trade and invoice documents for compliance screening.

IMPORTANT — DOCUMENT FORMAT DIVERSITY:
Invoice documents come in many different layouts and formats: commercial invoices, proforma invoices,
packing lists, combined invoice/packing list documents, shipping invoices, repair/RMA invoices,
intercompany transfers, and more. Do NOT assume any fixed layout. Read the actual labels and
headings in the document to identify fields and parties. The guidance below describes PATTERNS
you may encounter — not a guaranteed structure.

─── CONFIDENCE SCORES ───────────────────────────────────────────────────────────────────────────
Assign a confidence score (0.0–1.0) for every extracted value:
  0.95+  Field is clearly and unambiguously stated in the document
  0.80   Field required mild interpretation (abbreviation, merged cell, inferred from context)
  0.50   Field is uncertain — multiple interpretations possible, or partially legible
  0.00   Field is absent or completely unreadable

─── CRITICAL COMPLIANCE FIELDS ─────────────────────────────────────────────────────────────────
Pay extra attention to these fields — errors here have regulatory consequences:
  • consignor / consignee  — the physical parties to the shipment (may differ from seller/buyer)
  • end_user               — the actual final recipient of the goods
  • destination_country    — where goods will ultimately be used (may differ from consignee country)
  • hs_code                — Harmonized System tariff code (e.g. "9015.80.20.00")
  • eccn                   — Export Control Classification Number (e.g. "6A001.a.2.a.6")
  • serial_number          — unique device identifier, critical for traceability
  • incoterms              — determines who is responsible for the export declaration

─── ENTITY IDENTIFICATION ───────────────────────────────────────────────────────────────────────
Documents may present parties in multi-column layouts, nested sub-sections, or free-form text.
Always use the LABEL the document uses (e.g. "Consignor (Sender)", "Ship To", "Bill To") to
assign the correct role — do not guess from position alone.

Common role labels (not exhaustive — adapt to what the document actually says):
  consignor        "Consignor", "Sender", "Shipper", "Avsender", "Expéditeur"
                   The party physically handing over the goods for shipment.
  consignee        "Consignee", "Receiver", "Mottaker", "Destinataire"
                   The party physically receiving the shipment at destination.
  seller           "Seller", "Vendor", "Supplier", "Exporter", "Selger", "Vendeur"
                   The commercial seller — may or may not be the same as consignor.
  buyer            "Buyer", "Purchaser", "Importer", "Bill To", "Sold To", "Kjøper", "Acheteur"
                   The commercial buyer — may or may not be the same as consignee.
  end_user         "End User", "Ultimate Consignee", "End-User", "Sluttbruker"
                   The entity that will actually use the goods (critical for dual-use screening).
  delivery_address "Ship To", "Deliver To", "Notify Party", "Delivery Address", "Leveringsadresse"
                   A delivery or notification address that is not the buyer.
  other            Customs broker, freight forwarder, clearance agent, or any party that does not
                   fit the above roles. Examples: "For Customs clearance:", "Customs Agent:",
                   "Freight Forwarder:", "Déclarant en douane:". Capture these — they are
                   compliance-relevant even though they are not the buyer or seller.

A single document section may contain MULTIPLE parties (e.g. a consignee block that also names
a customs agent below it). Create a SEPARATE entity entry for each distinct party and role.
The same company may also appear in multiple roles — create one entry per role.

─── READING FLATTENED / OCR TEXT FROM MULTI-COLUMN DOCUMENTS ───────────────────────────────────
When a document with a multi-column layout (e.g. Consignor on the left, Consignee on the right)
has been converted to plain text or markdown by OCR, the column structure is often lost.
You must reconstruct which text belongs to which entity using the section headers as anchors.

THREE common flattening patterns — handle all of them:

  PATTERN 1 — Headers and data on the same lines (table-like OCR):
    "Consignor (Sender)          Notify Party     Consignee (Receiver)"
    "Acme Corp                   Port Authority   SERCEL"
    "12 Main St, Oslo                             17 Rue de Bel Air, Carquefou"
    → Read column by column. "Acme Corp" belongs to Consignor. "SERCEL" belongs to Consignee.
      Match each data row to its header column by horizontal position.

  PATTERN 2 — Sections linearised top-to-bottom:
    "Consignor (Sender)"
    "Acme Corp"
    "12 Main St, Oslo"
    "Consignee (Receiver)"
    "SERCEL"
    "17 Rue de Bel Air, Carquefou"
    → Everything between "Consignor (Sender)" and the next section header is consignor data.
      Everything between "Consignee (Receiver)" and the next section header is consignee data.

  PATTERN 3 — Mixed / partially structured:
    "Consignor (Sender) | Consignee (Receiver)"
    "Acme Corp | SERCEL"
    "Oslo, Norway | Carquefou, France"
    → Pipe characters (|) or similar separators often indicate original column boundaries.
      Use them to split lines and assign each part to the correct header.

KEY RULE: A section header such as "Consignor (Sender)" or "Consignee (Receiver)" acts as a
label for ALL the name, address, phone, email and contact lines that follow it — until the next
clearly different section begins. Never assign consignee address lines to the consignor or vice
versa just because they appear physically close in the flattened text.

If you are uncertain which column a line belongs to, assign low confidence (≤ 0.6) and note
the ambiguity in the comments field.

─── PO NUMBER / ORDER REFERENCE ─────────────────────────────────────────────────────────────────
The purchase order or reference number appears under many different labels and may stand alone
as a prominent reference in the header area (upper left or right) of the document.

Common labels (not exhaustive — adapt to what the document says):
  "PO", "P.O.", "PO No.", "PO #", "PO Number", "Purchase Order", "Purchase Order No."
  "Order No.", "Order Number", "Order ID", "Ord. No."
  "Your Ref", "Your Reference", "Your Order No.", "Customer Reference"
  "Our Ref", "Our Reference", "Our Order No."
  "Reference", "Ref.", "Ref No.", "Ref. No.", "Reference No."
  "ID", "ID No.", "ID-No.", "Document ID"
  "Contract No.", "Project No.", "Job No.", "Work Order"

Header-area rule: if a short alphanumeric code (typically 6-20 characters) appears prominently
in the header WITHOUT any of the above labels, but is clearly distinct from the invoice number
and is formatted as a reference (e.g. "PO-2024-1234", "ORD-789", "4500012345"), it is likely
the PO or order reference -- extract it with lower confidence (0.6-0.7).

The PO number identifies the buyer's order on their side; the invoice number is the seller's
reference. Do not confuse them — they are separate fields.

─── TARIFF CODES AND ECCN ───────────────────────────────────────────────────────────────────────
HS codes and ECCNs may appear in multiple places:
  1. A document-level "Instructions" or "Notes" section (e.g. "Tariff code: 9015.80.20.00")
  2. Directly in the line-item table columns
  3. Both places (should agree; flag discrepancies in comments)

If a code appears in the instructions/notes section but NOT in individual line items, apply it to
ALL lines (it is a document-level declaration covering all goods). If individual lines have their
own codes, use those per-line values.

─── LINE ITEMS ──────────────────────────────────────────────────────────────────────────────────
Extract ACTUAL GOODS only. Ignore packaging entries that describe the shipping container rather
than the goods inside it. Common packaging indicators: "Carton", "Cardboard box", "Pallet",
"Crate", "Case", "Box N×N×N cm/mm" without a product description or value.

Each serialised item is a separate line even if grouped under a common box or piece number.
Carry hs_code, eccn, and country_of_origin from the document-level or table header to all lines
where these fields are absent.

─── DATE EXTRACTION ─────────────────────────────────────────────────────────────────────────────
Look for the invoice date in these locations (in order of preference):
  1. A clearly labelled field: "Invoice Date", "Date", "Datum", "Dato", "Date of Issue"
  2. The document title or heading (e.g. "Invoice No. 1234 - 15 March 2025")
  3. A date near the invoice number or reference number in the header area
  4. A creation / issue date in the letterhead, footer, or document metadata
  5. A YYYYMMDD or YYYY-MM-DD pattern embedded in a reference code, document ID, or order number.
     For example: "SIR-20240111PE-E17" encodes 2024-01-11; "REF-20250315-001" encodes 2025-03-15.
     Only extract the date from a reference code if the 8-digit sequence forms a plausible
     calendar date (valid month 01-12, valid day 01-31). Use lower confidence (0.5-0.7) for
     dates derived from reference codes since this is an inference, not a labelled field.
     Do NOT use today's date or any fabricated date as a fallback — return null if no date is found.
Always normalise to YYYY-MM-DD format. If only a month and year are found, use the first day of
that month (e.g. "March 2025" → "2025-03-01").

─── INSTRUCTIONS / NOTES SECTIONS ──────────────────────────────────────────────────────────────
Many invoices include a free-text "Instructions" or "Notes" section separate from the main table.
  • instructions: Capture the FULL TEXT of this section verbatim (or near-verbatim). This is
    stored separately for audit purposes.
  • comments:     Summarise the compliance-critical elements from the instructions and any other
    analytical observations (RMA numbers, licence references, "AWAIT LICENCE", "EAR99",
    end-use statements, restrictions, discrepancies, suspicious addresses, etc.).
These two fields overlap intentionally — instructions is the raw source, comments is your analysis.

─── VAT / MOMS / TVA ────────────────────────────────────────────────────────────────────────────
  • vat_amount: The total VAT/moms/TVA amount stated on the invoice, in the invoice currency.
                Return as a decimal string (e.g. "35625.00"). Null if VAT is not charged, zero-rated,
                or not stated separately.
  • vat_rate:   The VAT rate as a percentage string (e.g. "25%", "0%", "VAT Exempt",
                "Zero-rated", "Not applicable"). Null if not mentioned at all.
  Common labels: "VAT", "Moms", "MVA", "TVA", "GST", "Sales Tax", "Tax", "Avgift"
  If the invoice explicitly states "VAT: 0" or "No VAT", set vat_amount to "0" and vat_rate to "0%".

─── SIGNATORIES ─────────────────────────────────────────────────────────────────────────────────
Extract persons who have SIGNED or are explicitly named as AUTHORISING the document.
Common indicators: signature blocks, "Signed by:", "Authorised by:", "Authorised signatory:",
"Name:", "For and on behalf of:", "Signature:", a printed name below a signature line.
Create one entity entry per signatory:
  role:        signatory
  entity_type: person
  name:        the person's name (required — skip if name is illegible or truly absent)
  address / phone / email / country: include only if explicitly stated for that person
Do NOT extract general contact persons, account managers, or company representatives unless
they have explicitly signed or been named as the authorising party for this document.

─── TRANSPORT AND INCOTERMS ─────────────────────────────────────────────────────────────────────
Transport mode inference:
  "By Air", "Air Freight", "AWB", "Airway Bill"        → air
  "By Sea", "Ocean Freight", "B/L", "Bill of Lading"   → sea
  "By Road", "Road", "Truck", "CMR", "Groupage"        → road
  "Rail", "By Rail"                                     → rail
  "Courier", "DHL", "FedEx", "UPS", "Express"          → courier

─── COUNTRY CODES ───────────────────────────────────────────────────────────────────────────────
Always use ISO 3166-1 alpha-2 (e.g. "NO", "US", "FR", "MY", "RU", "CN").
Infer from city/region names when the country is not explicit (e.g. "Carquefou" → "FR").

─── HIGH-RISK COUNTRIES (COMPLIANCE ESCALATION) ────────────────────────────────────────────────
Treat mentions of sanctioned/high-risk geographies as compliance-critical.
Examples include (not exhaustive): North Korea (KP/DPRK), Russia (RU), Belarus (BY),
Iran (IR), Syria (SY), Cuba (CU), Venezuela (VE), Crimea/Donetsk/Luhansk regions.

If any of these appear in destination, consignee/end-user context, delivery address,
instructions, or other shipment-relevant text:
  • Explicitly call this out in comments with the country/region name.
  • Do NOT write comments that imply "low risk" or "routine shipment".
  • If country assignment is uncertain, keep low confidence and mention ambiguity.

─── COMMENTS ────────────────────────────────────────────────────────────────────────────────────
Use the comments field for anything compliance-relevant that does not fit structured fields:
  • Licence references or "AWAIT LICENCE" notices
  • RMA / repair / return shipment indicators
  • Goods returning to origin (may be exempt from export control in some jurisdictions)
  • Discrepancies between document sections
  • Sanctioned-region delivery addresses
  • HS code inconsistent with description

Return ONLY valid JSON matching the specified schema. No explanation, no markdown fences.\
"""

INVOICE_EXTRACTION_USER_TEMPLATE = """\
Extract structured fields from the following invoice document.

IMPORTANT: Replace ALL confidence values with your actual confidence estimates (0.0–1.0).
Do NOT leave confidence as 0.0 unless you genuinely have zero confidence in a field.
A confidence of 0.95 means you are very certain; 0.5 means uncertain; 0.0 means absent/unknown.

Return a JSON object with this exact structure:
{{
  "invoice_number": {{"value": "string or null", "confidence": 0.95}},
  "invoice_date": {{"value": "YYYY-MM-DD or null", "confidence": 0.95}},
  "total_amount": {{"value": "decimal string or null", "confidence": 0.95}},
  "currency": {{"value": "ISO 4217 code or null", "confidence": 0.95}},
  "incoterms": {{"value": "EXW|FOB|CIF|DDP|DAP|... or null", "confidence": 0.95}},
  "transport_mode": {{"value": "sea|air|road|rail|courier|unknown or null", "confidence": 0.95}},
  "destination_country": {{"value": "ISO 3166-1 alpha-2 or null", "confidence": 0.95}},
  "po_number": {{"value": "string or null", "confidence": 0.95}},
  "vat_amount": {{"value": "decimal string or null", "confidence": 0.95}},
  "vat_rate": {{"value": "'25%' / '0%' / 'VAT Exempt' or null", "confidence": 0.95}},
  "instructions": {{"value": "verbatim instructions/notes text or null", "confidence": 0.95}},
  "comments": "Free text with compliance observations, ambiguities, or unusual findings. Null if nothing to note.",
  "entities": [
    {{
      "name": "string",
      "role": "seller|buyer|consignor|consignee|end_user|delivery_address|signatory|other",
      "entity_type": "company|person|vessel|aircraft",
      "country": "ISO 3166-1 alpha-2 or null",
      "address": "full address string or null",
      "phone": "phone number or null",
      "email": "email address or null",
      "confidence": 0.95
    }}
  ],
  "lines": [
    {{
      "description": "string or null",
      "product_code": "internal part/item number or null",
      "hs_code": "Harmonized System tariff code (e.g. 8517.12.00) or null",
      "eccn": "Export Control Classification Number (e.g. 5E002) or null",
      "serial_number": "device serial number or null",
      "model_number": "model or part number or null",
      "country_of_origin": "ISO 3166-1 alpha-2 or null",
      "quantity": "decimal string or null",
      "unit_of_measure": "pcs|kg|m|l|set|... or null",
      "unit_price": "decimal string or null",
      "total_price": "decimal string or null",
      "currency": "ISO 4217 code for this line's amounts (e.g. USD, EUR, NOK) or null if same as invoice currency",
      "confidence": 0.95
    }}
  ]
}}

INVOICE DOCUMENT:
{invoice_text}
"""


_MIME_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}

_VISION_USER_TEMPLATE = """\
Extract structured fields from the trade/invoice document shown in the image.

The IMAGE is the primary source — read all text, numbers, tables, addresses and labels directly
from it. The structured transcription at the bottom was generated from the same image by a
Vision OCR step; use it as a secondary cross-check to verify party names, addresses, amounts,
and codes. When image and transcription disagree, trust the image.

When the document uses a multi-column layout (e.g. Consignor on the left, Consignee on the right),
read each column independently using its header label to assign the correct role — do not let
column position alone determine the role. Apply all guidance from the system prompt about entity
roles, instructions sections, packaging lines, and HS/ECCN inheritance.

IMPORTANT: Replace ALL confidence values with your actual estimates (0.0–1.0).
Do NOT leave confidence as 0.0 unless you genuinely cannot find a field.
A value of 0.95 means very certain; 0.5 means uncertain; 0.0 means absent/unknown.

Return a JSON object with this exact structure:
{{
  "invoice_number": {{"value": "string or null", "confidence": 0.95}},
  "invoice_date": {{"value": "YYYY-MM-DD or null", "confidence": 0.95}},
  "total_amount": {{"value": "decimal string or null", "confidence": 0.95}},
  "currency": {{"value": "ISO 4217 code or null", "confidence": 0.95}},
  "incoterms": {{"value": "EXW|FOB|CIF|DDP|DAP|... or null", "confidence": 0.95}},
  "transport_mode": {{"value": "sea|air|road|rail|courier|unknown or null", "confidence": 0.95}},
  "destination_country": {{"value": "ISO 3166-1 alpha-2 or null", "confidence": 0.95}},
  "po_number": {{"value": "string or null", "confidence": 0.95}},
  "vat_amount": {{"value": "decimal string or null", "confidence": 0.95}},
  "vat_rate": {{"value": "'25%' / '0%' / 'VAT Exempt' or null", "confidence": 0.95}},
  "instructions": {{"value": "verbatim instructions/notes text or null", "confidence": 0.95}},
  "comments": "Free text for compliance notes, ambiguities, unusual findings. Null if nothing.",
  "entities": [
    {{
      "name": "string",
      "role": "seller|buyer|consignor|consignee|end_user|delivery_address|signatory|other",
      "entity_type": "company|person|vessel|aircraft",
      "country": "ISO 3166-1 alpha-2 or null",
      "address": "full address string or null",
      "phone": "phone number or null",
      "email": "email address or null",
      "confidence": 0.95
    }}
  ],
  "lines": [
    {{
      "description": "string or null",
      "product_code": "internal part/item number or null",
      "hs_code": "Harmonized System tariff code (e.g. 8517.12.00) or null",
      "eccn": "Export Control Classification Number (e.g. 5E002) or null",
      "serial_number": "device serial number or null",
      "model_number": "model or part number or null",
      "country_of_origin": "ISO 3166-1 alpha-2 or null",
      "quantity": "decimal string or null",
      "unit_of_measure": "pcs|kg|m|l|set|... or null",
      "unit_price": "decimal string or null",
      "total_price": "decimal string or null",
      "currency": "ISO 4217 code for this line's amounts (e.g. USD, EUR, NOK) or null if same as invoice currency",
      "confidence": 0.95
    }}
  ]
}}

STRUCTURED TRANSCRIPTION (cross-check reference — extracted from the same image via Vision OCR):
{ocr_text}
"""


def build_openai_vision_messages(
    image_path: Path,
    ocr_text: str,
) -> list[dict]:
    """Bygg OpenAI vision-melding med bilde + JSON-schema.

    Brukes for PNG/JPG-fakturaer der bildet er primærkilden.
    """
    import base64

    ext = image_path.suffix.lstrip(".").lower()
    media_type = _MIME_TYPES.get(ext, "image/png")
    image_data = base64.b64encode(image_path.read_bytes()).decode()

    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{image_data}",
                        "detail": "high",
                    },
                },
                {
                    "type": "text",
                    "text": _VISION_USER_TEMPLATE.format(
                        ocr_text=ocr_text[:6_000] if ocr_text else "(not available)",
                    ),
                },
            ],
        }
    ]


def build_claude_vision_messages(
    image_path: Path,
    ocr_text: str,
) -> list[dict]:
    """Bygg Anthropic Claude vision-melding med bilde + JSON-schema."""
    import base64

    ext = image_path.suffix.lstrip(".").lower()
    media_type = _MIME_TYPES.get(ext, "image/png")
    image_data = base64.b64encode(image_path.read_bytes()).decode()

    return [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": _VISION_USER_TEMPLATE.format(
                        ocr_text=ocr_text[:6_000] if ocr_text else "(not available)",
                    ),
                },
            ],
        }
    ]


def build_extraction_messages(invoice_text: str) -> list[dict[str, str]]:
    """Bygg meldingsliste for LLM-kallet."""
    return [
        {
            "role": "user",
            "content": INVOICE_EXTRACTION_USER_TEMPLATE.format(
                invoice_text=invoice_text[:12_000],
            ),
        },
    ]
