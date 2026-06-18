"""Felles datamodeller for dokumentparsing."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class ParserMethod(str, enum.Enum):
    """Hvilken metode som ble brukt for å hente ut tekst."""

    DIGITAL = "digital"  # PDF med tekstlag
    OCR = "ocr"  # Skannet PDF eller bilde-OCR
    HYBRID = "hybrid"  # Blanding av digital og OCR
    SPREADSHEET = "spreadsheet"  # Excel-fil lest direkte av Docling


class SourceFileType(str, enum.Enum):
    """Filformat for det opplastede dokumentet."""

    PDF = "pdf"
    XLSX = "xlsx"
    IMAGE = "image"  # PNG, JPEG osv. — behandles med OCR-pipeline

    @classmethod
    def from_filename(cls, filename: str) -> SourceFileType:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext == "xlsx":
            return cls.XLSX
        if ext in {"png", "jpg", "jpeg", "tiff", "bmp", "webp"}:
            return cls.IMAGE
        return cls.PDF


@dataclass(slots=True)
class ParsedPage:
    """En enkelt side/ark fra dokumentet."""

    page_number: int
    text: str
    method: ParserMethod


@dataclass(slots=True)
class ParsedDocument:
    """Resultatet av dokumentparsing."""

    text: str
    method: ParserMethod
    page_count: int
    file_type: SourceFileType = SourceFileType.PDF
    pages: list[ParsedPage] = field(default_factory=list)
    ocr_pages: int = 0

    @property
    def is_ocr(self) -> bool:
        return self.ocr_pages > 0
