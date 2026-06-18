"""
Regex-basert heuristisk ekstraktor for invoice-felter.

Kjøres uavhengig av LLM-ekstraksjon og gir et sikkerhetsnett for felt
som er lette å finne med mønstergjenkjenning men som LLM-en kan misse
på grunn av rar Markdown-formatering fra Docling.

Dekker fem felt med høy presisjon:
  email         ~100% presisjon — entydig format med '@'
  hs_code       ~95%  presisjon — 4+2(+2-4) sifre med punktum
  eccn          ~90%  presisjon — siffel + A-E + tre sifre
  serial_number ~85%  presisjon — prefiks-drevet (S/N:, Serial:, osv.)
  po_number     ~80%  presisjon — bredt sett av PO/ordre-etiketter

Utelatt bevisst (for mange falske positiver på fakturadata):
  telefonnummer, fakturanummer, beløp
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── Kompilerte mønstre ────────────────────────────────────────────────────────

# RFC 5322-light: fanger de aller fleste reelle epostadresser.
_RE_EMAIL = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")

# HS-koder: 4 sifre, punktum, 2 sifre, valgfritt punktum + 2-4 sifre.
# Eksempler: 8517.12  |  8517.12.00  |  8471.30.0000
_RE_HS = re.compile(r"\b(\d{4}\.\d{2}(?:\.\d{2,4})?)\b")

# ECCN: siffel (kategori) + A-E (gruppe) + tre sifre.
# Eksempler: 3A001  |  5E002  |  4D001  |  7A994
# Valgfri subpost-suffiks: .a, .b1, osv.
_RE_ECCN = re.compile(r"\b([0-9][ABCDE][0-9]{3}(?:\.[a-z][0-9]?)?)\b")

# EAR99 er en spesiell "ingen lisens"-betegnelse — ikke ECCN-format men
# fremkommer ofte ved siden av andre ECCN-koder.
_RE_EAR99 = re.compile(r"\bEAR99\b", re.IGNORECASE)

# Serienummer: prefiks-drevet. Gruppen etter prefiks er serienummeret.
# Krever minst 4 tegn etter prefiks for å unngå falske treff på kortere koder.
_RE_SERIAL = re.compile(
    r"(?:S/?N|Ser(?:ial)?\.?\s*(?:No\.?|Number|Nr\.?)?)[:\s]+([A-Z0-9][A-Z0-9\-\/]{3,})",
    re.IGNORECASE,
)

# Vanlige ISO 4217-valutakoder som forekommer i handelsfakturaer.
# Sortert etter lengde (lengst først) for å unngå deltreff (f.eks. "NOK" før "NO").
_COMMON_CURRENCIES = (
    "USD",
    "EUR",
    "NOK",
    "GBP",
    "JPY",
    "CHF",
    "CAD",
    "AUD",
    "SGD",
    "MYR",
    "DKK",
    "SEK",
    "HKD",
    "CNY",
    "INR",
    "BRL",
    "ZAR",
    "AED",
    "SAR",
    "KWD",
    "QAR",
    "THB",
    "IDR",
    "PHP",
    "NZD",
    "MXN",
    "TWD",
    "KRW",
    "TRY",
    "PLN",
    "CZK",
    "HUF",
)

# Regex: valutakode som eget ord, gjerne fulgt av/etterfulgt av et tall,
# eller som en del av benevnelse som "US$" eller "EUR ".
_RE_CURRENCY = re.compile(
    r"\b(" + "|".join(_COMMON_CURRENCIES) + r")\b"
    r"|US\$"  # US$ → USD
    r"|\bEUR\b",  # reservert for fullstendighet
    re.IGNORECASE,
)

# PO-nummer / ordrereferanse — bredt sett av etiketter (se system-prompt).
# Krav: minst 3 tegn etter etiketten for å unngå falske treff.
# Sekvensen tillater bokstaver, sifre, bindestrek, skråstrek og punktum.
# Etiketter: PO/P.O., Purchase Order, Order ID/No/Number, Your/Our Ref,
#            Customer Ref, Reference No., Contract No., Job No., Work Order, ID-No.
_RE_PO = re.compile(
    r"(?:"
    r"P\.?\s*O\.?\s*(?:No\.?|Number|#|Nr\.?)?"
    r"|Purchase\s+Order\s*(?:No\.?|Number|#)?"
    r"|Order\s+(?:ID|No\.?|Number|Nr\.?|#)"
    r"|(?:Your|Our)\s+(?:Ref(?:erence)?|Order)\s*(?:No\.?|Nr\.?|#)?"
    r"|(?:Customer|Client)\s+(?:Ref(?:erence)?|Order)\s*(?:No\.?|Nr\.?|#)?"
    r"|Ref(?:erence)?\s+No\.?"
    r"|Contract\s+No\.?"
    r"|Job\s+No\.?"
    r"|Work\s+Order\s*(?:No\.?|#)?"
    r"|ID[-\s]No\.?"
    r")"
    r"\s*[:\s#]*\s*"
    r"([A-Z0-9][A-Z0-9\-\/\.]{2,})",
    re.IGNORECASE,
)

# Consignee / Consignor — vanlig på fraktdokumenter og eksportfakturaer.
# Fanger én linje med navn etter etiketten; adressen ignoreres her (LLM tar den).
# Consignor → seller-rolle, Consignee → buyer-rolle.
_RE_CONSIGNOR = re.compile(
    r"(?:Consignor|Shipper|Avsender|Eksport[øo]r)[:\s]+([^\n\r]{3,80})",
    re.IGNORECASE,
)
_RE_CONSIGNEE = re.compile(
    r"(?:Consignee|Ultimate\s+Consignee|Mottaker|Importør)[:\s]+([^\n\r]{3,80})",
    re.IGNORECASE,
)


# ── Resultat-dataklasse ───────────────────────────────────────────────────────


@dataclass
class HeuristicResult:
    """Samling av verdier funnet via regex-søk i rå tekst."""

    emails: list[str] = field(default_factory=list)
    hs_codes: list[str] = field(default_factory=list)
    eccn_codes: list[str] = field(default_factory=list)
    serial_numbers: list[str] = field(default_factory=list)
    # Entitetsnavn funnet via Consignor/Consignee-etiketter.
    # Format: liste av (navn, rolle) — rolle er "seller" eller "buyer".
    entity_hints: list[tuple[str, str]] = field(default_factory=list)
    # Mest hyppige valutakode funnet i teksten (ISO 4217), eller None.
    # Brukes til å propagere dokument-valuta til linjer uten valuta.
    currency: str | None = None
    # PO-nummer / ordrereferanse (første treff med kjent etikett).
    po_number: str | None = None

    def is_empty(self) -> bool:
        return not any(
            [
                self.emails,
                self.hs_codes,
                self.eccn_codes,
                self.serial_numbers,
                self.entity_hints,
                self.currency,
                self.po_number,
            ]
        )


# ── Ekstraktor ────────────────────────────────────────────────────────────────


class HeuristicExtractor:
    """Trekker ut felter fra rå tekst med regex — ingen nettverkskall."""

    def extract(self, text: str) -> HeuristicResult:
        """Kjør alle mønstre mot teksten og returner dedupliserte funn.

        Bruker dict.fromkeys() for å bevare rekkefølgen (første forekomst)
        mens duplikater elimineres — viktig for linjetilordning i merger.
        """
        emails = list(dict.fromkeys(m.lower() for m in _RE_EMAIL.findall(text)))

        hs_codes = list(dict.fromkeys(_RE_HS.findall(text)))

        eccn_codes = list(dict.fromkeys(m.upper() for m in _RE_ECCN.findall(text)))
        if _RE_EAR99.search(text) and "EAR99" not in eccn_codes:
            eccn_codes.append("EAR99")

        serial_numbers = list(dict.fromkeys(m.upper().strip() for m in _RE_SERIAL.findall(text)))

        entity_hints: list[tuple[str, str]] = []
        for m in _RE_CONSIGNOR.finditer(text):
            name = m.group(1).strip().rstrip(",;")
            if name:
                entity_hints.append((name, "seller"))
        for m in _RE_CONSIGNEE.finditer(text):
            name = m.group(1).strip().rstrip(",;")
            if name:
                entity_hints.append((name, "buyer"))
        # Dedupliser på (navn, rolle)
        entity_hints = list(dict.fromkeys(entity_hints))

        # Valuta: finn alle koder, velg den mest hyppige (flest forekomster).
        # Normaliser "US$" → "USD".
        currency_counts: dict[str, int] = {}
        for raw in _RE_CURRENCY.findall(text):
            code = "USD" if raw.upper() == "US$" else raw.upper()
            if code in _COMMON_CURRENCIES:
                currency_counts[code] = currency_counts.get(code, 0) + 1
        currency = max(currency_counts, key=currency_counts.__getitem__) if currency_counts else None

        # PO-nummer: bruk første treff med kjent etikett.
        # Flere treff kan indikere at dokumentet gjengir referansen flere ganger;
        # vi foretrekker det første (normalt i header-området).
        po_number: str | None = None
        for m in _RE_PO.finditer(text):
            candidate = m.group(1).strip()
            # Utelukk kandidater som ser ut som ISO-valutakoder (f.eks. "USD", "NOK")
            if candidate.upper() in _COMMON_CURRENCIES:
                continue
            po_number = candidate
            break

        return HeuristicResult(
            emails=emails,
            hs_codes=hs_codes,
            eccn_codes=eccn_codes,
            serial_numbers=serial_numbers,
            entity_hints=entity_hints,
            currency=currency,
            po_number=po_number,
        )
