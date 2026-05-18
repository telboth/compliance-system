"""
Datamodeller for LLM-ekstraksjon av invoice-felter.

Hvert felt har en tilhørende konfidens (0.0–1.0). Felt under
confidence_threshold (default 0.8 fra Settings) flagges automatisk
for manuell review i extraction_service.

Disse modellene er input/output til LLM-klientene — de serialiseres ikke
direkte til databasen. Konvertering til DB-modeller skjer i extraction_service.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class FieldValue(BaseModel):
    """Et enkelt felt med verdi og konfidensscore."""

    value: str | None = None
    confidence: Confidence = 0.0


class ExtractedEntity(BaseModel):
    """En part identifisert i invoicen (kjøper, selger, sluttbruker, osv.)."""

    name: str
    role: str
    entity_type: str = "company"
    country: str | None = None
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    confidence: Confidence = 0.0


class ExtractedLine(BaseModel):
    """En vare- eller tjenestelinje i invoicen."""

    description: str | None = None
    product_code: str | None = None
    hs_code: str | None = None
    eccn: str | None = None
    serial_number: str | None = None
    model_number: str | None = None
    country_of_origin: str | None = None
    quantity: str | None = None
    unit_of_measure: str | None = None
    unit_price: str | None = None
    total_price: str | None = None
    currency: str | None = None   # ISO 4217 — arves fra faktura-nivå hvis ikke oppgitt per linje
    confidence: Confidence = 0.0


class InvoiceExtractionResult(BaseModel):
    """Komplett ekstraksjonsresultat for én invoice.

    Felt med konfidens under terskelen samles i low_confidence_fields
    slik at extraction_service kan eskalere dem til manuell review uten
    å måtte iterere over alle felter.
    """

    invoice_number: FieldValue = Field(default_factory=FieldValue)
    invoice_date: FieldValue = Field(default_factory=FieldValue)
    total_amount: FieldValue = Field(default_factory=FieldValue)
    currency: FieldValue = Field(default_factory=FieldValue)

    # Forsendelse og transport
    incoterms: FieldValue = Field(default_factory=FieldValue)
    transport_mode: FieldValue = Field(default_factory=FieldValue)
    destination_country: FieldValue = Field(default_factory=FieldValue)
    po_number: FieldValue = Field(default_factory=FieldValue)

    # MVA/moms
    vat_amount: FieldValue = Field(default_factory=FieldValue)
    vat_rate: FieldValue = Field(default_factory=FieldValue)

    # Verbatim instruksjoner/notater fra dokumentet
    instructions: FieldValue = Field(default_factory=FieldValue)

    # LLM-kommentarer om ekstraksjonens kvalitet eller uvanlige funn
    comments: str | None = None

    entities: list[ExtractedEntity] = Field(default_factory=list)
    lines: list[ExtractedLine] = Field(default_factory=list)

    # Samlet konfidens — gjennomsnitt av alle skalare felt
    overall_confidence: Confidence = 0.0

    # Navn på felt der konfidens < confidence_threshold
    low_confidence_fields: list[str] = Field(default_factory=list)

    # Token-forbruk for kostnadssporing
    input_tokens: int = 0
    output_tokens: int = 0
    model_id: str = ""

    def compute_derived(self, threshold: float = 0.8) -> None:
        """Beregn overall_confidence og low_confidence_fields in-place.

        Kalles av LLM-klientene etter at alle felt er satt.

        Konfidenslogikk:
          - Confidence 0.0 betyr «fraværende eller helt uleselig» (jf. system-prompten).
            Slike felt anses som ikke til stede i dokumentet og teller IKKE
            i gjennomsnittet — et manglende Incoterms-felt skal ikke straffe
            den totale scoren.
          - Felt med confidence > 0 er «funnet» og teller i gjennomsnittet,
            uavhengig av om verdien er None eller ikke (LLM kan gi lav,
            men ikke-null, konfidens til felt den er usikker på).
          - Et felt havner i low_confidence_fields bare hvis det ER funnet
            (confidence > 0) OG konfidens < terskel.
        """
        scalar_fields = {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "incoterms": self.incoterms,
            "transport_mode": self.transport_mode,
            "destination_country": self.destination_country,
            "vat_amount": self.vat_amount,
            "vat_rate": self.vat_rate,
        }

        # Felt med confidence > 0 er «funnet» — 0.0 betyr fraværende/uleselig
        found = {k: v for k, v in scalar_fields.items() if v.confidence > 0.0}
        if found:
            self.overall_confidence = round(
                sum(f.confidence for f in found.values()) / len(found), 3
            )
        else:
            self.overall_confidence = 0.0

        # Lav-konfidens-liste: kun felt som er funnet men med konfidens under terskelen
        self.low_confidence_fields = [
            name for name, field in found.items()
            if field.confidence < threshold
        ]
