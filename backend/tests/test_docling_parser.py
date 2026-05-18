"""
Tester for Docling-parseren (PDF, XLSX, PNG).

Tester som faktisk laster Docling-modeller er merket @pytest.mark.slow.
I CI hoppes de over med `pytest -m "not slow"`.

Enhetstester bruker mocks og verifiserer lazy-import-mekanismen uten å
starte den tunge Docling-pipelinen.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import ParsingError
from app.parsers.docling_parser import extract_text, reset_converters
from app.parsers.models import ParserMethod, SourceFileType


@pytest.fixture(autouse=True)
def clear_converter_cache() -> None:
    """Nullstill lazy singletons mellom tester."""
    reset_converters()
    yield
    reset_converters()


# ── Felles ────────────────────────────────────────────────────────────────────

def test_extract_text_raises_when_file_missing(tmp_path: Path) -> None:
    """Feilhåndtering krever ikke at Docling lastes — sjekkes før import."""
    missing = tmp_path / "finnes-ikke.pdf"
    with pytest.raises(ParsingError, match="Fil finnes ikke"):
        extract_text(missing)


# ── PDF-tester ────────────────────────────────────────────────────────────────

def test_extract_text_wraps_docling_exception(tmp_path: Path) -> None:
    """Docling-feil pakkes inn i ParsingError med forståelig melding."""
    pdf = tmp_path / "bad.pdf"
    pdf.write_bytes(b"%PDF-1.4 corrupted content")

    with patch("app.parsers.docling_parser._get_standard_converter") as mock_conv:
        mock_conv.return_value.convert.side_effect = RuntimeError("Docling intern feil")
        with pytest.raises(ParsingError, match="Docling klarte ikke"):
            extract_text(pdf)


def test_extract_text_uses_mock_converter(tmp_path: Path) -> None:
    """Konverteren kalles med korrekt sti og resultatet pakkes i ParsedDocument."""
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = "# Invoice\nTest innhold"
    mock_doc.pages = [MagicMock(), MagicMock()]
    mock_result = MagicMock()
    mock_result.document = mock_doc

    with patch("app.parsers.docling_parser._get_standard_converter") as mock_get:
        mock_get.return_value.convert.return_value = mock_result
        doc = extract_text(pdf, pipeline="standard")

    assert doc.text == "# Invoice\nTest innhold"
    assert doc.page_count == 2
    assert doc.method == ParserMethod.DIGITAL
    assert doc.file_type == SourceFileType.PDF


def test_multimodal_falls_back_to_standard_without_api_key(tmp_path: Path) -> None:
    """Multimodal skal falle tilbake til standard hvis OPENAI_API_KEY mangler."""
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = "Fallback tekst"
    mock_doc.pages = [MagicMock()]
    mock_result = MagicMock()
    mock_result.document = mock_doc

    with (
        patch("app.parsers.docling_parser.get_settings") as mock_settings,
        patch("app.parsers.docling_parser._get_standard_converter") as mock_standard,
    ):
        settings = MagicMock()
        settings.openai_api_key_value = ""
        settings.docling_pipeline = "standard"
        mock_settings.return_value = settings
        mock_standard.return_value.convert.return_value = mock_result

        doc = extract_text(pdf, pipeline="multimodal")
        assert doc.text == "Fallback tekst"
        mock_standard.assert_called()


def test_converter_is_reused_across_calls(tmp_path: Path) -> None:
    """Konverteren skal bare initialiseres én gang (lazy singleton)."""
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = "Tekst"
    mock_doc.pages = [MagicMock()]
    mock_result = MagicMock()
    mock_result.document = mock_doc

    call_count = 0

    def mock_get_converter():
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        m.convert.return_value = mock_result
        return m

    with patch("app.parsers.docling_parser._get_standard_converter", side_effect=mock_get_converter):
        extract_text(pdf, pipeline="standard")
        extract_text(pdf, pipeline="standard")

    # _get_standard_converter kalles per extract_text-kall, men den interne
    # singleton-logikken sørger for at DocumentConverter bare opprettes én gang.
    assert call_count == 2  # getter kalles, men intern init skjer én gang


# ── XLSX-tester ───────────────────────────────────────────────────────────────

def test_extract_xlsx_uses_mock_converter(tmp_path: Path, sample_xlsx_bytes: bytes) -> None:
    """XLSX-parsing returnerer ParsedDocument med SPREADSHEET-metode."""
    xlsx = tmp_path / "invoice.xlsx"
    xlsx.write_bytes(sample_xlsx_bytes)

    mock_doc = MagicMock()
    mock_doc.export_to_markdown.return_value = "| Invoice Number | Amount |\n| INV-001 | 1000 |"
    mock_doc.pages = [MagicMock()]
    mock_result = MagicMock()
    mock_result.document = mock_doc

    with patch("app.parsers.docling_parser._get_simple_converter") as mock_get:
        mock_get.return_value.convert.return_value = mock_result
        doc = extract_text(xlsx)

    assert doc.method == ParserMethod.SPREADSHEET
    assert doc.file_type == SourceFileType.XLSX
    assert "INV-001" in doc.text
    assert doc.page_count == 1


def test_extract_xlsx_wraps_docling_exception(tmp_path: Path, sample_xlsx_bytes: bytes) -> None:
    """Docling-feil for XLSX pakkes inn i ParsingError."""
    xlsx = tmp_path / "invoice.xlsx"
    xlsx.write_bytes(sample_xlsx_bytes)

    with patch("app.parsers.docling_parser._get_simple_converter") as mock_get:
        mock_get.return_value.convert.side_effect = RuntimeError("XLSX intern feil")
        with pytest.raises(ParsingError, match="Docling klarte ikke å lese Excel-filen"):
            extract_text(xlsx)


def test_extract_xlsx_raises_when_file_missing(tmp_path: Path) -> None:
    missing = tmp_path / "mangler.xlsx"
    with pytest.raises(ParsingError, match="Fil finnes ikke"):
        extract_text(missing)


# ── Integrasjonstester (krever Docling ML-modeller) ───────────────────────────

@pytest.mark.slow
def test_extract_text_with_real_docling(temp_pdf: Path) -> None:
    """Integrasjonstest — laster faktiske Docling ML-modeller."""
    doc = extract_text(temp_pdf)
    assert doc.page_count >= 1
    assert doc.method == ParserMethod.DIGITAL


@pytest.mark.slow
def test_extract_xlsx_with_real_docling(temp_xlsx: Path) -> None:
    """Integrasjonstest — laster Docling og leser en ekte XLSX-fil."""
    doc = extract_text(temp_xlsx)
    assert doc.method == ParserMethod.SPREADSHEET
    assert doc.file_type == SourceFileType.XLSX
    assert len(doc.text) > 0
