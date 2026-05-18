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
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING

import anyio
from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.errors import NotFoundError, ParsingError
from app.core.logging import get_logger
from app.models.entity import Entity, EntityRole, EntityType
from app.models.invoice import ComplianceScore, Invoice, InvoiceDirection, InvoiceStatus
from app.models.invoice_line import InvoiceLine
from app.parsers import parse_pdf
from app.services.invoice_note_service import apply_invoice_notes
from app.services.pipeline_event_service import append_pipeline_event
from app.services import audit_service
from app.services import file_storage

if TYPE_CHECKING:
    from app.schemas.invoice import EntityUpdate, InvoiceFieldsUpdate, InvoiceLineUpdate

logger = get_logger(__name__)

RAW_TEXT_PREVIEW_LENGTH = 500

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
    r"\b\d{1,3}(?:[.,\s]\d{3})+[.,]\d{1,2}\b"   # 1 234,56
    r"|\b\d+[.,]\d{2}\b",                          # 12.34
)

# Minimum krav for at et dokument «ser ut som en faktura»
_MIN_WORD_COUNT = 20
_MIN_KEYWORD_HITS = 1
_MIN_AMOUNT_HITS = 2     # nok hvis ingen nøkkelord, men mange beløp


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

    return False, (
        "Dokumentet inneholder ingen faktura-nøkkelord eller beløp. "
        "Last opp en PDF/bilde av en faktura."
    )


# ── Opplasting (synkron — rask) ───────────────────────────────────────────────

async def upload_invoice_only(
    session: AsyncSession,
    upload: UploadFile,
    direction: InvoiceDirection,
    customer_id: uuid.UUID | None = None,
) -> Invoice:
    """Lagre fil og opprett invoice-rad. Returnerer umiddelbart — parsing skjer i bakgrunnen."""
    storage_path, size_bytes, _file_type = await file_storage.save_upload(upload)
    invoice = Invoice(
        pdf_path=str(storage_path),
        original_filename=upload.filename,
        file_size_bytes=size_bytes,
        direction=direction,
        status=InvoiceStatus.UPLOADED,
        customer_id=customer_id,
    )
    session.add(invoice)
    await session.flush()  # Gir invoice.id
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
    return await get_invoice(session, invoice.id)


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
            timeout_seconds = int(getattr(settings, "parsing_timeout_seconds", 180) or 180)
            parsed = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: parse_pdf(storage_path),
                ),
                timeout=max(30, timeout_seconds),
            )
        except asyncio.TimeoutError:
            prev_status = invoice.status.value
            invoice.status = InvoiceStatus.PARSING_FAILED
            invoice.parsing_error = (
                f"Parsing timed out etter {max(30, timeout_seconds)} sekunder."
            )
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
            return   # stopp pipeline — ikke gå videre til ekstraksjon

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

async def review_invoice(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    *,
    decision: str,
    reason: str,
    actor: str = "system",
) -> Invoice:
    """Sett en manuell review-beslutning (approved / blocked) på en invoice.

    Kun fakturaer med status 'screened' kan reviewes. Beslutningen logges i
    den hash-kjedete revisjonsloggen og settes som ny status på invoicen.
    """
    from datetime import datetime, timezone

    invoice = await get_invoice(session, invoice_id)

    allowed_statuses = {
        InvoiceStatus.SCREENED,
        InvoiceStatus.APPROVED,
        InvoiceStatus.BLOCKED,
    }
    if invoice.status not in allowed_statuses:
        from app.core.errors import ApplicationError
        raise ApplicationError(
            f"Kan ikke reviewe en invoice med status '{invoice.status.value}'. "
            "Invoicen må være screenet først.",
            details={"invoice_id": str(invoice_id), "status": invoice.status.value},
        )

    prev_status = invoice.status.value
    invoice.status = InvoiceStatus.APPROVED if decision == "approved" else InvoiceStatus.BLOCKED
    invoice.review_decision = decision
    invoice.review_reason = reason
    invoice.reviewed_by = actor
    invoice.reviewed_at = datetime.now(tz=timezone.utc)

    await audit_service.log(
        session,
        action=f"invoice.{decision}",
        actor=actor,
        invoice_id=invoice.id,
        details={
            "decision": decision,
            "reason": reason,
            "prev_status": prev_status,
        },
    )

    # ── In-app varsel for review-beslutning ───────────────────────────────────
    from app.services import notification_service
    inv_label = invoice.original_filename or invoice.invoice_number or str(invoice_id)[:8]
    decision_icon = "✓" if decision == "approved" else "🔒"
    await notification_service.create(
        session,
        message=f"{decision_icon} {inv_label} ble {'godkjent' if decision == 'approved' else 'blokkert'} av {actor}",
        level="info" if decision == "approved" else "warn",
        invoice_id=invoice.id,
        target_roles=["controller", "admin"],
    )

    await session.commit()
    logger.info(
        "invoice_reviewed",
        invoice_id=str(invoice_id),
        decision=decision,
        actor=actor,
    )
    return await get_invoice(session, invoice_id)


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
    destination_country: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str | None = None,
    sort_dir: str = "desc",
) -> tuple[list[Invoice], int]:
    """List invoices med paginering og filtrering."""
    count_stmt = select(func.count()).select_from(Invoice)
    list_stmt = select(Invoice)

    def _apply_filters(stmt):  # type: ignore[no-untyped-def]
        if status is not None:
            stmt = stmt.where(Invoice.status == status)
        if direction is not None:
            stmt = stmt.where(Invoice.direction == direction)
        if compliance_score is not None:
            stmt = stmt.where(Invoice.compliance_score == compliance_score)
        if vat_note_status:
            stmt = stmt.where(Invoice.vat_note_status == vat_note_status)
        if email_note_status:
            stmt = stmt.where(Invoice.email_note_status == email_note_status)
        if destination_country is not None:
            country_filter = "".join(ch for ch in destination_country.upper() if ch.isalpha())[:2]
            if country_filter:
                stmt = stmt.where(
                    func.upper(func.trim(Invoice.destination_country)) == country_filter
                )
        if date_from is not None:
            stmt = stmt.where(Invoice.invoice_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Invoice.invoice_date <= date_to)
        return stmt

    count_stmt = _apply_filters(count_stmt)
    list_stmt = _apply_filters(list_stmt)

    sort_map = {
        "created_at": Invoice.created_at,
        "invoice_date": Invoice.invoice_date,
        "total_amount": Invoice.total_amount,
        "status": Invoice.status,
        "compliance_score": Invoice.compliance_score,
        "vat_note_status": Invoice.vat_note_status,
        "email_note_status": Invoice.email_note_status,
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
