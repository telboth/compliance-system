"""
Forretningslogikk for invoices.

Opplasting er asynkron: upload_invoice_only() lagrer filen og oppretter
databaseraden umiddelbart, mens parse_invoice_in_background() kjøres som
BackgroundTask og oppdaterer status når Docling er ferdig.

Flyt:
  1. POST /invoices/upload → lagrer fil, status=UPLOADED, returnerer 201
  2. BackgroundTask starter → status=PARSING
  3. Docling parser i thread-pool (blokkerer ikke event-loopen)
  4. status=PARSED (eller PARSING_FAILED)
  5. Frontend poller GET /invoices/{id} hvert 3. sek til status er ferdig
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
from fastapi import UploadFile
from sqlalchemy import func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import ApplicationError, NotFoundError, ParsingError
from app.core.logging import get_logger
from app.models.entity import Entity, EntityRole, EntityType
from app.models.invoice import (
    ApprovalState,
    ComplianceScore,
    Invoice,
    InvoiceDirection,
    InvoiceStatus,
    compute_approval_state,
)
from app.models.invoice_line import InvoiceLine
from app.parsers import parse_pdf
from app.services import audit_service, file_storage
from app.services.invoice_note_service import apply_invoice_notes
from app.services.pipeline_event_service import append_pipeline_event

if TYPE_CHECKING:
    from app.schemas.invoice import (
        EntityUpdate,
        InvoiceFieldsUpdate,
        InvoiceLineUpdate,
    )

logger = get_logger(__name__)

RAW_TEXT_PREVIEW_LENGTH = 500

APPROVAL_STATES = {"pending", "approved", "blocked", "not_required", "assessing"}


def _sha256_for_file(path: Path) -> str:
    """Beregn SHA-256 for filinnhold (brukes til duplikatvern ved upload)."""
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _find_duplicate_invoice(
    session: AsyncSession,
    *,
    file_sha256: str,
    size_bytes: int,
) -> Invoice | None:
    """Finn eksisterende invoice med samme binære innhold.

    1) Foretrekk direkte hash-match (nye rader)
    2) Fallback for legacy-rader uten hash: sammenlign filer med samme størrelse
    """
    exact_stmt = select(Invoice).where(Invoice.file_sha256 == file_sha256).order_by(Invoice.created_at.desc()).limit(1)
    exact = (await session.execute(exact_stmt)).scalar_one_or_none()
    if exact is not None:
        return exact

    legacy_stmt = (
        select(Invoice)
        .where(Invoice.file_sha256.is_(None), Invoice.file_size_bytes == size_bytes)
        .order_by(Invoice.created_at.desc())
        .limit(200)
    )
    legacy_candidates = list((await session.execute(legacy_stmt)).scalars().all())
    for candidate in legacy_candidates:
        path = Path(candidate.pdf_path)
        if not path.exists():
            continue
        try:
            # V3: SHA-256 er synkron disk-I/O — kjør i thread-pool for å ikke blokkere event-loopen.
            candidate_hash = await anyio.to_thread.run_sync(lambda p=path: _sha256_for_file(p))
            if candidate_hash == file_sha256:
                return candidate
        except OSError:
            continue
    return None


def derive_approval_state(
    status: InvoiceStatus,
    compliance_score: ComplianceScore | None,
) -> str:
    """Entydig approval-state for UI/filter/sort (streng for API)."""
    return compute_approval_state(status, compliance_score).value


# ── Faktura-gjenkjenning (Trinn 1: tekstsjekk etter parsing) ──────────────────

# Nøkkelord som sterkt indikerer at dokumentet er en faktura
_INVOICE_KEYWORDS_RE = re.compile(
    r"\b("
    r"invoice|faktura|bill|receipt|kvittering|rechnung|facture|fattura|factura"
    r"|total|amount|beløp|belop|subtotal|vat|mva|tax|skatt"
    r"|invoice\s*(?:no|nr|#|number)|faktura\s*(?:no|nr|#|nummer)"
    r"|order\s*(?:no|nr|#)|purchase\s*order|po\s*#"
    r"|quantity|antall|unit\s*price|stykpris"
    r"|payment\s*due|forfallsdato|due\s*date"
    r"|seller|buyer|vendor|supplier|leverandør|kjøper"
    r")\b",
    re.IGNORECASE,
)

# Tall som ligner beløp: 1 234,56 / 1.234,56 / 12.34 / 12,34 osv.
_AMOUNT_RE = re.compile(
    r"\b\d{1,3}(?:[.,\s]\d{3})+[.,]\d{1,2}\b"  # 1 234,56
    r"|\b\d+[.,]\d{2}\b",  # 12.34
)

# Minimum krav for at et dokument «ser ut som en faktura»
_MIN_WORD_COUNT = 20
_MIN_KEYWORD_HITS = 1
_MIN_AMOUNT_HITS = 2  # nok hvis ingen nøkkelord, men mange beløp


def _looks_like_invoice(text: str | None) -> tuple[bool, str | None]:
    """Heuristisk sjekk: er teksten sannsynligvis en faktura?

    Logikk (første match vinner):
    1. Tomt → avvis
    2. Inneholder faktura-nøkkelord → godkjenn (uavhengig av lengde)
    3. Inneholder nok beløpsmønstre → godkjenn
    4. For kort (< MIN_WORD_COUNT ord) → avvis
    5. Ingen nøkkelord OG ingen beløp → avvis

    Returns:
        (True, None)              → ser ut som faktura, fortsett
        (False, avvisnings-grunn) → trolig ikke en faktura
    """
    if not text or not text.strip():
        return False, "Dokumentet er tomt eller inneholder ingen lesbar tekst."

    # Sjekk nøkkelord og beløp FØRST — sterk signal overstyrer lengde-kravet
    keyword_hits = len(_INVOICE_KEYWORDS_RE.findall(text))
    if keyword_hits >= _MIN_KEYWORD_HITS:
        return True, None

    amount_hits = len(_AMOUNT_RE.findall(text))
    if amount_hits >= _MIN_AMOUNT_HITS:
        return True, None

    # Ingen sterke signaler — bruk ordlengde som siste sjekk
    word_count = len(text.split())
    if word_count < _MIN_WORD_COUNT:
        return False, (
            f"Dokumentet er for kort ({word_count} ord) og mangler faktura-nøkkelord. "
            "Sjekk at riktig fil ble lastet opp."
        )

    return False, ("Dokumentet inneholder ingen faktura-nøkkelord eller beløp. Last opp en PDF/bilde av en faktura.")


# ── Opplasting (synkron — rask) ───────────────────────────────────────────────


async def upload_invoice_only(
    session: AsyncSession,
    upload: UploadFile,
    direction: InvoiceDirection,
    customer_id: uuid.UUID | None = None,
) -> tuple[Invoice, bool]:
    """Lagre fil og opprett invoice-rad. Returnerer umiddelbart — parsing skjer i bakgrunnen."""
    storage_path, size_bytes, _file_type = await file_storage.save_upload(upload)
    # V3: SHA-256 er synkron disk-I/O — kjør i thread-pool for å ikke blokkere event-loopen.
    file_sha256 = await anyio.to_thread.run_sync(lambda p=storage_path: _sha256_for_file(p))

    existing = await _find_duplicate_invoice(
        session,
        file_sha256=file_sha256,
        size_bytes=size_bytes,
    )
    if existing is not None:
        try:
            storage_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("duplicate_upload_temp_file_delete_failed", path=str(storage_path))
        logger.info(
            "invoice_upload_duplicate_detected",
            duplicate_invoice_id=str(existing.id),
            filename=upload.filename,
        )
        return await get_invoice(session, existing.id), True

    invoice = Invoice(
        pdf_path=str(storage_path),
        original_filename=upload.filename,
        file_size_bytes=size_bytes,
        file_sha256=file_sha256,
        direction=direction,
        status=InvoiceStatus.UPLOADED,
        customer_id=customer_id,
    )
    session.add(invoice)
    try:
        await session.flush()  # Gir invoice.id
    except IntegrityError:
        await session.rollback()
        existing = await _find_duplicate_invoice(
            session,
            file_sha256=file_sha256,
            size_bytes=size_bytes,
        )
        try:
            storage_path.unlink(missing_ok=True)
        except OSError:
            logger.warning("duplicate_upload_temp_file_delete_failed", path=str(storage_path))
        if existing is not None:
            logger.info(
                "invoice_upload_duplicate_detected_race",
                duplicate_invoice_id=str(existing.id),
                filename=upload.filename,
            )
            return await get_invoice(session, existing.id), True
        raise

    await audit_service.log(
        session,
        action="invoice.uploaded",
        invoice_id=invoice.id,
        details={
            "filename": upload.filename,
            "size_bytes": size_bytes,
            "direction": direction.value,
        },
    )
    await session.commit()
    await session.refresh(invoice)
    logger.info("invoice_created", invoice_id=str(invoice.id))

    # Eager-load relasjoner for serialisering
    return await get_invoice(session, invoice.id), False


# ── Parsing (asynkron bakgrunnsoppgave) ───────────────────────────────────────


async def parse_invoice_in_background(invoice_id: uuid.UUID, storage_path: Path) -> None:
    """BackgroundTask — oppretter egen DB-sesjon og parser med Docling i thread-pool.

    Docling er CPU-bundet og blokkerende; vi kjører den via run_in_executor
    slik at FastAPI-event-loopen ikke blokkeres mens OCR pågår.
    """
    async with get_session_factory()() as session:
        invoice = await get_invoice(session, invoice_id)
        prev_status = invoice.status.value
        invoice.status = InvoiceStatus.PARSING
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="parsing",
            action="started",
            status_from=prev_status,
            status_to=InvoiceStatus.PARSING.value,
        )
        await session.commit()

        try:
            loop = asyncio.get_running_loop()
            settings = get_settings()
            timeout_seconds = settings.parsing_timeout_seconds
            parsed = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: parse_pdf(storage_path),
                ),
                timeout=max(30, timeout_seconds),
            )
        except TimeoutError:
            prev_status = invoice.status.value
            invoice.status = InvoiceStatus.PARSING_FAILED
            invoice.parsing_error = f"Parsing timed out etter {max(30, timeout_seconds)} sekunder."
            await append_pipeline_event(
                session,
                invoice_id=invoice.id,
                stage="parsing",
                action="failed",
                status_from=prev_status,
                status_to=InvoiceStatus.PARSING_FAILED.value,
                message=invoice.parsing_error,
                payload={"timeout_seconds": max(30, timeout_seconds)},
            )
            await session.commit()
            logger.warning(
                "invoice_parsing_timeout",
                invoice_id=str(invoice_id),
                timeout_seconds=max(30, timeout_seconds),
            )
            return
        except ParsingError as exc:
            prev_status = invoice.status.value
            invoice.status = InvoiceStatus.PARSING_FAILED
            invoice.parsing_error = exc.message
            await append_pipeline_event(
                session,
                invoice_id=invoice.id,
                stage="parsing",
                action="failed",
                status_from=prev_status,
                status_to=InvoiceStatus.PARSING_FAILED.value,
                message=exc.message,
            )
            await session.commit()
            logger.warning(
                "invoice_parsing_failed",
                invoice_id=str(invoice_id),
                error=exc.message,
            )
            return
        except Exception as exc:
            prev_status = invoice.status.value
            invoice.status = InvoiceStatus.PARSING_FAILED
            invoice.parsing_error = str(exc)
            await append_pipeline_event(
                session,
                invoice_id=invoice.id,
                stage="parsing",
                action="failed",
                status_from=prev_status,
                status_to=InvoiceStatus.PARSING_FAILED.value,
                message=str(exc),
            )
            await session.commit()
            logger.exception("invoice_parsing_unexpected_error", invoice_id=str(invoice_id))
            return

        prev_status = invoice.status.value
        invoice.raw_text = parsed.text
        invoice.parsing_error = None

        # ── Trinn 1: heuristisk faktura-gjenkjenning ──────────────────────────
        is_invoice, rejection_reason = _looks_like_invoice(parsed.text)
        if not is_invoice:
            invoice.status = InvoiceStatus.NOT_INVOICE
            invoice.parsing_error = rejection_reason
            await append_pipeline_event(
                session,
                invoice_id=invoice.id,
                stage="parsing",
                action="rejected",
                status_from=prev_status,
                status_to=InvoiceStatus.NOT_INVOICE.value,
                message=rejection_reason,
                payload={
                    "method": parsed.method.value,
                    "page_count": parsed.page_count,
                    "text_length": len(parsed.text),
                    "reason": "not_invoice_heuristic",
                },
            )
            await audit_service.log(
                session,
                action="invoice.rejected_not_invoice",
                invoice_id=invoice.id,
                details={
                    "reason": rejection_reason,
                    "stage": "post_parsing",
                    "text_length": len(parsed.text),
                },
            )
            await session.commit()
            logger.info(
                "invoice_rejected_not_invoice",
                invoice_id=str(invoice_id),
                stage="post_parsing",
                reason=rejection_reason,
                text_length=len(parsed.text),
            )
            return  # stopp pipeline — ikke gå videre til ekstraksjon

        invoice.status = InvoiceStatus.PARSED
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="parsing",
            action="completed",
            status_from=prev_status,
            status_to=InvoiceStatus.PARSED.value,
            payload={
                "method": parsed.method.value,
                "page_count": parsed.page_count,
                "text_length": len(parsed.text),
            },
        )
        await audit_service.log(
            session,
            action="invoice.parsed",
            invoice_id=invoice.id,
            details={
                "method": parsed.method.value,
                "page_count": parsed.page_count,
                "text_length": len(parsed.text),
            },
        )
        await session.commit()
        logger.info(
            "invoice_parsed",
            invoice_id=str(invoice_id),
            method=parsed.method.value,
            page_count=parsed.page_count,
            text_length=len(parsed.text),
        )
        try:
            from app.services.invoice_search_service import index_invoice

            await index_invoice(invoice_id)
        except Exception:
            logger.exception("invoice_search_index_failed_after_parse", invoice_id=str(invoice_id))

    # Auto-ekstraksjon: start LLM-ekstraksjon umiddelbart hvis konfigurert.
    # Kjøres utenfor try/except-blokken — parsing har lyktes på dette punktet.
    if get_settings().auto_extract_after_parse:
        try:
            from app.services.extraction_service import run_extraction

            async with get_session_factory()() as ext_session:
                await run_extraction(ext_session, invoice_id)
                logger.info("auto_extraction_completed", invoice_id=str(invoice_id))
        except Exception:
            # Feil i auto-ekstraksjon skal ikke påvirke parsing-statusen.
            logger.exception("auto_extraction_failed", invoice_id=str(invoice_id))


# ── Review-beslutning ─────────────────────────────────────────────────────────


async def escalate_invoice_risk_for_review(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    target_score: ComplianceScore,
    reason: str,
    actor: str = "system",
) -> Invoice:
    """Eskalér en grønn invoice til gul/rød og send den til manuell review."""
    invoice = await get_invoice(session, invoice_id)

    if target_score not in {ComplianceScore.YELLOW, ComplianceScore.RED}:
        raise ApplicationError(
            "target_score må være yellow eller red.",
            details={"invoice_id": str(invoice_id), "target_score": target_score.value},
        )

    if invoice.compliance_score != ComplianceScore.GREEN:
        raise ApplicationError(
            "Kun grønne invoices kan eskaleres manuelt.",
            details={
                "invoice_id": str(invoice_id),
                "current_score": invoice.compliance_score.value if invoice.compliance_score else None,
            },
        )

    if invoice.status in {
        InvoiceStatus.UPLOADED,
        InvoiceStatus.PARSING,
        InvoiceStatus.EXTRACTING,
        InvoiceStatus.SCREENING,
        InvoiceStatus.NOT_INVOICE,
    }:
        raise ApplicationError(
            f"Kan ikke eskalere invoice i status '{invoice.status.value}'.",
            details={"invoice_id": str(invoice_id), "status": invoice.status.value},
        )

    prev_status = invoice.status.value
    prev_score = invoice.compliance_score.value if invoice.compliance_score else None

    invoice.compliance_score = target_score
    invoice.status = InvoiceStatus.SCREENED
    invoice.review_decision = None
    invoice.review_reason = None
    invoice.reviewed_by = None
    invoice.reviewed_at = None

    await audit_service.log(
        session,
        action="invoice.risk_escalated",
        actor=actor,
        invoice_id=invoice.id,
        details={
            "from_score": prev_score,
            "to_score": target_score.value,
            "from_status": prev_status,
            "to_status": InvoiceStatus.SCREENED.value,
            "reason": reason,
        },
    )

    from app.services import notification_service

    inv_label = invoice.original_filename or invoice.invoice_number or str(invoice.id)[:8]
    await notification_service.create(
        session,
        message=f"⚠ {inv_label} ble manuelt eskalert til {target_score.value} av {actor}. Krever review.",
        level="warn",
        invoice_id=invoice.id,
        target_roles=["compliance_officer", "admin"],
    )

    await session.commit()
    logger.info(
        "invoice_risk_escalated",
        invoice_id=str(invoice_id),
        actor=actor,
        target_score=target_score.value,
    )
    return await get_invoice(session, invoice_id)


async def review_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    decision: str,
    reason: str,
    rule_reference: str,
    evidence_summary: str,
    deviation_approval: bool,
    actor: str = "system",
) -> Invoice:
    """Bakoverkompatibel delegasjon til dedikert review-service."""
    from app.services.invoice_review_service import review_invoice as _review_invoice

    return await _review_invoice(
        session,
        invoice_id,
        decision=decision,
        reason=reason,
        rule_reference=rule_reference,
        evidence_summary=evidence_summary,
        deviation_approval=deviation_approval,
        actor=actor,
    )


# ── Sletting ──────────────────────────────────────────────────────────────────


async def delete_invoice(session: AsyncSession, invoice_id: uuid.UUID) -> None:
    """Slett en invoice, tilhørende linjer/entiteter og filen fra disk."""
    invoice = await get_invoice(session, invoice_id)

    aio_path = anyio.Path(invoice.pdf_path)
    if await aio_path.exists():
        await aio_path.unlink()
        logger.info("invoice_file_deleted", path=invoice.pdf_path)

    await session.delete(invoice)
    await session.commit()
    logger.info("invoice_deleted", invoice_id=str(invoice_id))
    try:
        from app.services.invoice_search_service import delete_invoice_document

        await delete_invoice_document(invoice_id)
    except Exception:
        logger.exception("invoice_search_delete_failed", invoice_id=str(invoice_id))


# ── Henting og listing ────────────────────────────────────────────────────────


async def get_invoice(session: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
    """Hent en invoice med relasjoner. Reiser NotFoundError hvis ikke funnet."""
    stmt = (
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(selectinload(Invoice.lines), selectinload(Invoice.entities))
    )
    result = await session.execute(stmt)
    invoice = result.scalar_one_or_none()
    if invoice is None:
        raise NotFoundError(
            "Invoice ikke funnet.",
            details={"invoice_id": str(invoice_id)},
        )
    return invoice


async def list_invoices(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    status: InvoiceStatus | None = None,
    direction: InvoiceDirection | None = None,
    compliance_score: ComplianceScore | None = None,
    vat_note_status: str | None = None,
    email_note_status: str | None = None,
    approval_state: str | None = None,
    destination_country: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str | None = None,
    sort_dir: str = "desc",
) -> tuple[list[Invoice], int]:
    """List invoices med paginering og filtrering."""
    count_stmt = select(func.count()).select_from(Invoice)
    list_stmt = select(Invoice)

    # Bygg WHERE-betingelser én gang og legg dem på begge spørringer.
    conditions = []
    if status is not None:
        conditions.append(Invoice.status == status)
    if direction is not None:
        conditions.append(Invoice.direction == direction)
    if compliance_score is not None:
        conditions.append(Invoice.compliance_score == compliance_score)
    if vat_note_status:
        conditions.append(Invoice.vat_note_status == vat_note_status)
    if email_note_status:
        conditions.append(Invoice.email_note_status == email_note_status)
    if approval_state:
        if approval_state not in APPROVAL_STATES:
            conditions.append(literal(False))
        else:
            conditions.append(Invoice.approval_state == ApprovalState(approval_state))
    if destination_country is not None:
        country_filter = "".join(ch for ch in destination_country.upper() if ch.isalpha())[:2]
        if country_filter:
            conditions.append(func.upper(func.trim(Invoice.destination_country)) == country_filter)
    if date_from is not None:
        conditions.append(Invoice.invoice_date >= date_from)
    if date_to is not None:
        conditions.append(Invoice.invoice_date <= date_to)

    if conditions:
        count_stmt = count_stmt.where(*conditions)
        list_stmt = list_stmt.where(*conditions)

    sort_map = {
        "created_at": Invoice.created_at,
        "invoice_date": Invoice.invoice_date,
        "total_amount": Invoice.total_amount,
        "status": Invoice.status,
        "compliance_score": Invoice.compliance_score,
        "vat_note_status": Invoice.vat_note_status,
        "email_note_status": Invoice.email_note_status,
        "approval_state": Invoice.approval_state,
        "llm_note_preview": Invoice.llm_note_preview,
        "original_filename": Invoice.original_filename,
    }
    sort_col = sort_map.get((sort_by or "").strip().lower(), Invoice.created_at)
    is_asc = (sort_dir or "desc").lower() == "asc"
    list_stmt = list_stmt.order_by(
        sort_col.asc().nullslast() if is_asc else sort_col.desc().nullslast(),
        Invoice.created_at.desc(),
    )

    total = (await session.execute(count_stmt)).scalar_one()
    list_stmt = list_stmt.limit(limit).offset(offset)
    invoices = list((await session.execute(list_stmt)).scalars().all())
    return invoices, total


# ── Manuelle korrigeringer ────────────────────────────────────────────────────


async def update_invoice_fields(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    update: InvoiceFieldsUpdate,
) -> Invoice:
    """Oppdater ett eller flere headerfelt på en invoice manuelt.

    Kun felt som er eksplisitt satt i update-objektet oppdateres
    (exclude_none=True). Felt som ikke er med røres ikke.
    """
    invoice = await get_invoice(session, invoice_id)
    data = update.model_dump(exclude_none=True)
    for field, value in data.items():
        if field in {"total_amount", "vat_amount"} and isinstance(value, str):
            try:
                value = Decimal(value.replace(",", ".").replace(" ", ""))
            except InvalidOperation:
                continue
        setattr(invoice, field, value)

    apply_invoice_notes(invoice)
    await session.commit()
    try:
        from app.services.invoice_search_service import index_invoice

        await index_invoice(invoice.id)
    except Exception:
        logger.exception("invoice_search_index_failed_after_invoice_update", invoice_id=str(invoice.id))
    logger.info(
        "invoice_fields_manually_updated",
        invoice_id=str(invoice_id),
        fields=list(data.keys()),
    )
    return await get_invoice(session, invoice_id)


async def update_invoice_line(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    line_id: uuid.UUID,
    update: InvoiceLineUpdate,
) -> InvoiceLine:
    """Oppdater ett eller flere felt på en invoice-linje manuelt."""
    stmt = select(InvoiceLine).where(
        InvoiceLine.id == line_id,
        InvoiceLine.invoice_id == invoice_id,
    )
    result = await session.execute(stmt)
    line = result.scalar_one_or_none()
    if line is None:
        raise NotFoundError(
            "Invoice-linje ikke funnet.",
            details={"invoice_id": str(invoice_id), "line_id": str(line_id)},
        )

    data = update.model_dump(exclude_none=True)
    decimal_fields = {"quantity", "unit_price", "total_price"}
    uppercase_fields = {"currency", "country_of_origin"}

    for field, value in data.items():
        if field in decimal_fields and isinstance(value, str):
            try:
                value = Decimal(value.replace(",", ".").replace(" ", ""))
            except InvalidOperation:
                continue
        elif field in uppercase_fields and isinstance(value, str):
            value = value.upper()[:3] if field == "currency" else value.upper()[:2]
        setattr(line, field, value)

    await session.commit()
    await session.refresh(line)
    try:
        from app.services.invoice_search_service import index_invoice

        await index_invoice(invoice_id)
    except Exception:
        logger.exception("invoice_search_index_failed_after_line_update", invoice_id=str(invoice_id))
    logger.info(
        "invoice_line_manually_updated",
        invoice_id=str(invoice_id),
        line_id=str(line_id),
        fields=list(data.keys()),
    )
    return line


async def update_entity(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    update: EntityUpdate,
) -> Entity:
    """Oppdater ett eller flere felt på en entitet manuelt."""
    stmt = select(Entity).where(
        Entity.id == entity_id,
        Entity.invoice_id == invoice_id,
    )
    result = await session.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise NotFoundError(
            "Entitet ikke funnet.",
            details={"invoice_id": str(invoice_id), "entity_id": str(entity_id)},
        )

    data = update.model_dump(exclude_none=True)

    for field, value in data.items():
        if field == "role":
            try:
                value = EntityRole(value)
            except ValueError:
                continue
        elif field == "entity_type":
            try:
                value = EntityType(value)
            except ValueError:
                continue
        setattr(entity, field, value)

    parent_invoice = await get_invoice(session, invoice_id)
    apply_invoice_notes(parent_invoice)
    await session.commit()
    await session.refresh(entity)
    try:
        from app.services.invoice_search_service import index_invoice

        await index_invoice(invoice_id)
    except Exception:
        logger.exception("invoice_search_index_failed_after_entity_update", invoice_id=str(invoice_id))
    logger.info(
        "entity_manually_updated",
        invoice_id=str(invoice_id),
        entity_id=str(entity_id),
        fields=list(data.keys()),
    )
    return entity
