"""
Felles modell-typer, provider-enum og LLM-klient-ABC.

Konkrete klienter (claude.py, openai_client.py) arver fra LLMClient og
implementerer extract_invoice(). Alle tunge imports skjer lazy i de
konkrete klassene — denne filen importerer ingenting utenfor stdlib.
"""

from __future__ import annotations

import abc
import enum
from dataclasses import dataclass, field
from pathlib import Path

from app.llm.extraction import InvoiceExtractionResult


class LLMProvider(str, enum.Enum):
    """Tilgjengelige LLM-leverandører."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OLLAMA = "ollama"


@dataclass(slots=True, frozen=True)
class ModelInfo:
    """Metadata om en tilgjengelig modell."""

    provider: LLMProvider
    model_id: str
    display_name: str
    multimodal: bool = False
    context_window: int | None = None
    local: bool = False
    tags: list[str] = field(default_factory=list)


class LLMClient(abc.ABC):
    """Abstrakt baseklasse for alle LLM-klienter.

    Sprint 2 bruker bare extract_invoice(). Fremtidige sprinter kan
    legge til parse_agreement(), screening_explanation() osv.
    """

    @abc.abstractmethod
    async def extract_invoice(
        self,
        invoice_text: str,
        *,
        image_path: Path | None = None,
        confidence_threshold: float = 0.8,
    ) -> InvoiceExtractionResult:
        """Ekstraher strukturerte felter fra en invoice-tekst.

        Args:
            invoice_text:         Rå tekst fra Docling-parsing (eller tom streng).
            image_path:           Sti til originalbildet hvis filen er PNG/JPG.
                                  Når satt, brukes Vision API og bildet er primærkilden.
            confidence_threshold: Felt under denne verdien → low_confidence_fields.

        Returns:
            InvoiceExtractionResult med felt, konfidens og token-forbruk.
        """
