"""
Lagring av opplastede invoice-dokumenter på disk.

Støtter PDF, XLSX og bildefiler (PNG, JPEG). Vi bruker en UUID-basert sti for
å unngå problemer med spesialtegn i originalt filnavn. Originalnavnet lagres
i databasen.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.errors import FileTooLargeError, UnsupportedFileTypeError
from app.core.logging import get_logger
from app.parsers.models import SourceFileType

logger = get_logger(__name__)

# MIME-type → filtype-enum + extension som lagres på disk
_ALLOWED: dict[str, tuple[SourceFileType, str]] = {
    "application/pdf": (SourceFileType.PDF, ".pdf"),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        SourceFileType.XLSX,
        ".xlsx",
    ),
    # Noen klienter sender denne eldre MIME-typen for .xlsx
    "application/vnd.ms-excel": (SourceFileType.XLSX, ".xlsx"),
    # Bildefiler — PNG og JPEG er vanlig for scannede fakturaer
    "image/png": (SourceFileType.IMAGE, ".png"),
    "image/jpeg": (SourceFileType.IMAGE, ".jpg"),
    "image/jpg": (SourceFileType.IMAGE, ".jpg"),
}

# Magic bytes for signatursjekk — en tuple med gyldige prefiks per filtype.
# PDF starter alltid med "%PDF-"
# XLSX er en ZIP-fil og starter med PK\x03\x04 (ZIP local file header)
# PNG starter alltid med 8-byte signaturen \x89PNG\r\n\x1a\n
# JPEG starter alltid med FF D8 FF
_MAGIC: dict[SourceFileType, tuple[bytes, ...]] = {
    SourceFileType.PDF: (b"%PDF-",),
    SourceFileType.XLSX: (b"PK\x03\x04",),
    SourceFileType.IMAGE: (b"\x89PNG", b"\xff\xd8\xff"),
}


async def save_upload(upload: UploadFile) -> tuple[Path, int, SourceFileType]:
    """Lagre et opplastet invoice-dokument til konfigurert upload-katalog.

    Args:
        upload: FastAPI UploadFile fra endepunktet.

    Returns:
        (sti til lagret fil, filstørrelse i bytes, filtype-enum)

    Raises:
        UnsupportedFileTypeError: Hvis filtypen ikke er PDF eller XLSX.
        FileTooLargeError: Hvis filen overskrider konfigurert maks-størrelse.
    """
    settings = get_settings()
    content_type = (upload.content_type or "").split(";")[0].strip()

    if content_type not in _ALLOWED:
        raise UnsupportedFileTypeError(
            "Kun PDF og XLSX er støttet.",
            details={
                "content_type": content_type,
                "allowed": list(_ALLOWED.keys()),
            },
        )

    file_type, extension = _ALLOWED[content_type]

    contents = await upload.read()
    size = len(contents)

    if size > settings.max_upload_size_bytes:
        raise FileTooLargeError(
            f"Filen er større enn maks {settings.max_upload_size_mb} MB.",
            details={"size_bytes": size, "max_bytes": settings.max_upload_size_bytes},
        )

    if not any(contents.startswith(m) for m in _MAGIC[file_type]):
        raise UnsupportedFileTypeError(
            f"Filen ser ikke ut til å være en gyldig {file_type.value.upper()} "
            f"(feil filsignatur).",
            details={
                "expected_magic": [m.hex() for m in _MAGIC[file_type]],
                "got": contents[:8].hex(),
            },
        )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    storage_path = settings.upload_dir / f"{uuid.uuid4()}{extension}"
    storage_path.write_bytes(contents)

    logger.info(
        "invoice_document_stored",
        path=str(storage_path),
        file_type=file_type.value,
        size_bytes=size,
        original_filename=upload.filename,
    )
    return storage_path, size, file_type
