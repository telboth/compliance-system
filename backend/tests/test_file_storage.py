"""Tester for fillagring av opplastede invoice-dokumenter (PDF, XLSX, PNG)."""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi import UploadFile

from app.core.errors import FileTooLargeError, UnsupportedFileTypeError
from app.parsers.models import SourceFileType
from app.services import file_storage

# ── Hjelpefunksjon ────────────────────────────────────────────────────────────


def _make_upload(
    content: bytes,
    *,
    filename: str,
    content_type: str,
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers={"content-type": content_type},  # type: ignore[arg-type]
    )


# ── PDF-tester ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_upload_rejects_non_pdf_content_type(sample_pdf_bytes: bytes) -> None:
    upload = _make_upload(sample_pdf_bytes, filename="invoice.txt", content_type="text/plain")
    with pytest.raises(UnsupportedFileTypeError):
        await file_storage.save_upload(upload)


@pytest.mark.asyncio
async def test_save_upload_rejects_file_without_pdf_header() -> None:
    upload = _make_upload(b"NOT A PDF", filename="invoice.pdf", content_type="application/pdf")
    with pytest.raises(UnsupportedFileTypeError, match="feil filsignatur"):
        await file_storage.save_upload(upload)


@pytest.mark.asyncio
async def test_save_upload_rejects_oversized_file(sample_pdf_bytes: bytes, monkeypatch) -> None:
    settings = file_storage.get_settings()
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)
    upload = _make_upload(sample_pdf_bytes, filename="invoice.pdf", content_type="application/pdf")
    with pytest.raises(FileTooLargeError):
        await file_storage.save_upload(upload)


@pytest.mark.asyncio
async def test_save_upload_stores_valid_pdf(sample_pdf_bytes: bytes) -> None:
    upload = _make_upload(sample_pdf_bytes, filename="invoice.pdf", content_type="application/pdf")
    path, size, file_type = await file_storage.save_upload(upload)
    assert path.exists()
    assert size == len(sample_pdf_bytes)
    assert path.read_bytes().startswith(b"%PDF-")
    assert file_type == SourceFileType.PDF
    assert path.suffix == ".pdf"


# ── XLSX-tester ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_upload_stores_valid_xlsx(sample_xlsx_bytes: bytes) -> None:
    upload = _make_upload(
        sample_xlsx_bytes,
        filename="invoice.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    path, size, file_type = await file_storage.save_upload(upload)
    assert path.exists()
    assert size == len(sample_xlsx_bytes)
    # XLSX er ZIP-format — starter alltid med PK\x03\x04
    assert path.read_bytes().startswith(b"PK\x03\x04")
    assert file_type == SourceFileType.XLSX
    assert path.suffix == ".xlsx"


@pytest.mark.asyncio
async def test_save_upload_accepts_legacy_xlsx_mime(sample_xlsx_bytes: bytes) -> None:
    """Eldre MIME-type application/vnd.ms-excel skal også godtas for XLSX-filer."""
    upload = _make_upload(
        sample_xlsx_bytes,
        filename="invoice.xlsx",
        content_type="application/vnd.ms-excel",
    )
    path, size, file_type = await file_storage.save_upload(upload)
    assert file_type == SourceFileType.XLSX


@pytest.mark.asyncio
async def test_save_upload_rejects_xlsx_with_wrong_magic() -> None:
    """Fil med XLSX MIME men ugyldig signatur skal avvises."""
    upload = _make_upload(
        b"NOT AN XLSX FILE",
        filename="invoice.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    with pytest.raises(UnsupportedFileTypeError, match="feil filsignatur"):
        await file_storage.save_upload(upload)


# ── PNG-tester ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_save_upload_stores_valid_png() -> None:
    # Minimal gyldig PNG: 8-byte signatur + IHDR chunk
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"  # PNG signatur
        b"\x00\x00\x00\rIHDR"  # IHDR chunk-lengde + type
        b"\x00\x00\x00\x01"  # bredde = 1
        b"\x00\x00\x00\x01"  # høyde = 1
        b"\x08\x02\x00\x00\x00"  # bit depth, color type, etc.
        b"\x90wS\xde"  # CRC (ikke verifisert av signatursjekk)
    )
    upload = _make_upload(png_bytes, filename="scan.png", content_type="image/png")
    path, size, file_type = await file_storage.save_upload(upload)
    assert file_type == SourceFileType.IMAGE
    assert path.suffix == ".png"
