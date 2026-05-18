"""
Inngangsport for dokumentparsing (PDF og XLSX).

All parsing går gjennom Docling. `parse_document` er det eneste grensesnittet
resten av applikasjonen bruker — interne detaljer holdes innenfor parsers-modulen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.parsers.docling_parser import extract_text
from app.parsers.models import ParsedDocument


def parse_document(
    file_path: Path,
    pipeline: Literal["standard", "multimodal"] | None = None,
) -> ParsedDocument:
    """Parse et invoice-dokument (PDF eller XLSX) til strukturert tekst.

    Filtypen detekteres automatisk fra utvidelsen. Pipeline-parameteret gjelder
    kun for PDF; XLSX ignorerer det og leses alltid direkte av Docling.

    Args:
        file_path: Sti til filen på disk.
        pipeline:  Valgfri PDF-pipeline-override ("standard" | "multimodal").

    Returns:
        ParsedDocument med Markdown-tekst, filtype og metadata.
    """
    return extract_text(file_path, pipeline=pipeline)
