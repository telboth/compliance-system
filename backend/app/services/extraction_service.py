"""
Forretningslogikk for LLM-ekstraksjon av invoice-felter (Sprint 2).

Flyten:
1. Sett invoice.status = EXTRACTING
2. Hent cached raw_text fra databasen (satt av invoice_service i Sprint 1)
3. Kjør heuristisk ekstraksjon (sync, < 1 ms) og LLM-kall (async) parallelt
4. Merge resultatene — heuristikk fyller inn felt LLM mista, deduplicerer
5. Lagre strukturerte felter (InvoiceLine, Entity) og konfidensscore i DB
6. Sett invoice.status = EXTRACTED
7. Returner oppdatert invoice + ekstrasjonsresultat

Feilhåndtering:
  Enhver exception under ekstraksjon setter status EXTRACTION_FAILED og
  lagrer feilmeldingen i invoice.extraction_error — slik at controlleren
  ser hva som gikk galt uten å sjekke loggene.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Coroutine
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.logging import get_logger
from app.llm.extraction import InvoiceExtractionResult
from app.llm.factory import get_llm_client
from app.llm.heuristics import HeuristicExtractor
from app.llm.merger import merge
from app.models.entity import Entity, EntityRole, EntityType
from app.models.invoice import Invoice, InvoiceStatus
from app.models.invoice_line import InvoiceLine
from app.parsers.models import SourceFileType
from app.services import audit_service
from app.services.invoice_note_service import apply_invoice_notes
from app.services.invoice_service import get_invoice
from app.services.pipeline_event_service import append_pipeline_event

logger = get_logger(__name__)
_background_tasks: set[asyncio.Task[None]] = set()


def _schedule_background(coro: Coroutine[Any, Any, None]) -> None:
    """Opprett og behold referanse til background-task til den er ferdig."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _running_inside_celery_task() -> bool:
    """True nar koden kjores inne i en aktiv Celery-task-kontekst."""
    try:
        from celery import current_task

        return current_task is not None
    except Exception:
        return False


async def run_extraction(
    session: AsyncSession,
    invoice_id: uuid.UUID,
    model_id: str | None = None,
) -> tuple[Invoice, InvoiceExtractionResult]:
    """Kjør LLM-ekstraksjon på en invoice som allerede er parsert.

    Args:
        session:    Async DB-session.
        invoice_id: ID til invoicen som skal ekstraheres.
        model_id:   LLM-modell å bruke. None → system-standard fra Settings.

    Returns:
        (oppdatert invoice, ekstrasjonsresultat)

    Raises:
        NotFoundError:    Invoicen finnes ikke.
        ApplicationError: Invoicen har ingen rå tekst (ikke parsert ennå),
                          eller LLM-kallet feiler.
    """
    settings = get_settings()
    timeout_seconds = settings.extraction_timeout_seconds
    invoice = await get_invoice(session, invoice_id)

    if not invoice.raw_text:
        raise ApplicationError(
            "Invoicen har ingen parsert tekst — kjør parsing før ekstraksjon.",
            details={"invoice_id": str(invoice_id), "status": invoice.status.value},
        )

    active_model = model_id or settings.llm_primary_model
    client = get_llm_client(active_model)

    # Detekter om originalfilen er et bilde — sendes da til Vision API
    invoice_file_path = Path(invoice.pdf_path)
    file_type = SourceFileType.from_filename(invoice.original_filename or invoice.pdf_path)
    image_path = invoice_file_path if file_type == SourceFileType.IMAGE else None

    prev_status = invoice.status.value
    invoice.status = InvoiceStatus.EXTRACTING
    invoice.extraction_error = None
    await append_pipeline_event(
        session,
        invoice_id=invoice.id,
        stage="extracting",
        action="started",
        status_from=prev_status,
        status_to=InvoiceStatus.EXTRACTING.value,
        payload={"model": active_model},
    )
    await session.commit()

    try:
        # Heuristikk er synkron og rask — kjøres i executor for å ikke blokkere
        # event loop, og startes parallelt med LLM-kallet.
        loop = asyncio.get_running_loop()
        extractor = HeuristicExtractor()
        heuristic_task = loop.run_in_executor(None, extractor.extract, invoice.raw_text or "")

        llm_task = client.extract_invoice(
            invoice.raw_text or "",
            image_path=image_path,
            confidence_threshold=settings.confidence_threshold,
        )

        result, heuristic_result = await asyncio.wait_for(
            asyncio.gather(llm_task, heuristic_task),
            timeout=max(30, timeout_seconds),
        )

        result = merge(
            result,
            heuristic_result,
            raw_text=invoice.raw_text,
            threshold=settings.confidence_threshold,
            filename=invoice.original_filename,
        )
        result.compute_derived(threshold=settings.confidence_threshold)
    except TimeoutError as exc:
        prev_status = invoice.status.value
        invoice.status = InvoiceStatus.EXTRACTION_FAILED
        invoice.extraction_error = "LLM-ekstraksjon timet ut. Prøv re-ekstrahering eller bytt modell."
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="extracting",
            action="failed",
            status_from=prev_status,
            status_to=InvoiceStatus.EXTRACTION_FAILED.value,
            message=invoice.extraction_error,
            payload={"model": active_model, "timeout_seconds": timeout_seconds},
        )
        await audit_service.log(
            session,
            action="extraction.failed",
            invoice_id=invoice.id,
            details={"reason": "timeout", "model": active_model},
        )
        await session.commit()
        logger.warning(
            "invoice_extraction_timeout",
            invoice_id=str(invoice_id),
            model=active_model,
            timeout_seconds=timeout_seconds,
        )
        raise ApplicationError(
            "LLM-ekstraksjon timet ut.",
            details={
                "invoice_id": str(invoice_id),
                "model": active_model,
                "timeout_seconds": timeout_seconds,
            },
        ) from exc

    except Exception as exc:
        prev_status = invoice.status.value
        invoice.status = InvoiceStatus.EXTRACTION_FAILED
        invoice.extraction_error = str(exc)
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="extracting",
            action="failed",
            status_from=prev_status,
            status_to=InvoiceStatus.EXTRACTION_FAILED.value,
            message=str(exc),
            payload={"model": active_model},
        )
        await audit_service.log(
            session,
            action="extraction.failed",
            invoice_id=invoice.id,
            details={"reason": str(exc)[:200], "model": active_model},
        )
        await session.commit()
        logger.warning(
            "invoice_extraction_failed",
            invoice_id=str(invoice_id),
            model=active_model,
            error=str(exc),
        )
        raise

    await _persist_result(session, invoice, result)

    # ── AI Governance — logg AI-beslutning for EU AI Act-sporbarhet ──────────
    try:
        from app.services import ai_governance_service

        await ai_governance_service.upsert_decision_record(
            session,
            invoice_id=invoice.id,
            model_id=result.model_id or active_model,
            model_provider=settings.llm_primary_provider,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            overall_confidence=result.overall_confidence,
            low_confidence_fields=result.low_confidence_fields or [],
            raw_extraction_meta={
                "model_id": result.model_id,
                "overall_confidence": result.overall_confidence,
                "low_confidence_fields": result.low_confidence_fields,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            },
        )
    except Exception:
        logger.exception("ai_governance_record_failed", invoice_id=str(invoice.id))

    # Avbryt pipeline dersom Trinn 2 avviste dokumentet
    if invoice.status == InvoiceStatus.NOT_INVOICE:
        return invoice, result

    try:
        from app.services.invoice_search_service import index_invoice

        await index_invoice(invoice.id)
    except Exception:
        logger.exception("invoice_search_index_failed_after_extraction", invoice_id=str(invoice.id))

    logger.info(
        "invoice_extracted",
        invoice_id=str(invoice_id),
        model=result.model_id,
        overall_confidence=result.overall_confidence,
        low_confidence_fields=result.low_confidence_fields,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )

    # Auto-screening: start sanksjonsscreening automatisk hvis konfigurert.
    # For Celery-kjoring ma fallback kjores awaited (ikke create_task),
    # ellers kan tasken bli droppet nar event-loopen stoppes.
    if settings.auto_screen_after_extract:
        if settings.use_celery_background:
            try:
                from app.tasks.screen_entities import run as screen_entities_task

                screen_entities_task.delay(str(invoice_id))
                logger.info("auto_screening_queued_celery", invoice_id=str(invoice_id))
            except Exception:
                logger.exception(
                    "auto_screening_celery_enqueue_failed_fallback_inline",
                    invoice_id=str(invoice_id),
                )
                await _run_screening_after_extraction(invoice_id)
                logger.info("auto_screening_fallback_completed", invoice_id=str(invoice_id))
        else:
            try:
                # Viktig: i Celery-worker kan create_task bli avbrutt når parent task
                # avsluttes. Kjor derfor awaited i worker-kontekst for å unngå
                # "extracted men aldri screened".
                if _running_inside_celery_task():
                    await _run_screening_after_extraction(invoice_id)
                    logger.info(
                        "auto_screening_completed_inline_worker",
                        invoice_id=str(invoice_id),
                    )
                else:
                    _schedule_background(_run_screening_after_extraction(invoice_id))
                    logger.info("auto_screening_queued", invoice_id=str(invoice_id))
            except Exception:
                logger.exception(
                    "auto_screening_async_schedule_failed_fallback_inline",
                    invoice_id=str(invoice_id),
                )
                await _run_screening_after_extraction(invoice_id)
                logger.info("auto_screening_fallback_completed", invoice_id=str(invoice_id))

    return invoice, result


async def _run_screening_after_extraction(invoice_id: uuid.UUID) -> None:
    """Hjelpefunksjon: kjor sanksjonsscreening i bakgrunnen etter ekstraksjon."""
    from app.core.database import get_session_factory
    from app.services import screening_service as _screening_service
    from app.services.screening_service import ScreeningLockUnavailableError

    async with get_session_factory()() as screen_session:
        try:
            await _screening_service.screen_invoice(screen_session, invoice_id)
        except ScreeningLockUnavailableError:
            logger.info(
                "auto_screening_skipped_lock_conflict",
                invoice_id=str(invoice_id),
            )
        except Exception:
            logger.exception(
                "auto_screening_failed",
                invoice_id=str(invoice_id),
            )


async def _persist_result(
    session: AsyncSession,
    invoice: Invoice,
    result: InvoiceExtractionResult,
) -> None:
    """Lagre ekstraksjonsresultatet til databasen."""

    # Skalare felt på invoice
    if result.invoice_number.value:
        invoice.invoice_number = result.invoice_number.value
    if result.total_amount.value:
        invoice.total_amount = _to_decimal(result.total_amount.value)
    if result.currency.value:
        invoice.currency = result.currency.value[:3].upper()
    if result.invoice_date.value:
        invoice.invoice_date = _to_date(result.invoice_date.value)

    # Forsendelse og transport
    if result.incoterms.value:
        invoice.incoterms = result.incoterms.value[:10].upper()
    if result.transport_mode.value:
        invoice.transport_mode = result.transport_mode.value.lower()
    if result.destination_country.value:
        invoice.destination_country = result.destination_country.value[:2].upper()
    if result.po_number.value:
        invoice.po_number = result.po_number.value
    if result.comments:
        invoice.comments = result.comments
    if result.instructions.value:
        invoice.instructions = result.instructions.value
    if result.vat_amount.value:
        invoice.vat_amount = _to_decimal(result.vat_amount.value)
    if result.vat_rate.value:
        invoice.vat_rate = result.vat_rate.value[:20]

    # Konfidens, metadata og token-forbruk
    invoice.extraction_confidence = {
        "invoice_number": result.invoice_number.confidence,
        "invoice_date": result.invoice_date.confidence,
        "total_amount": result.total_amount.confidence,
        "currency": result.currency.confidence,
        "incoterms": result.incoterms.confidence,
        "transport_mode": result.transport_mode.confidence,
        "destination_country": result.destination_country.confidence,
        "vat_amount": result.vat_amount.confidence,
        "vat_rate": result.vat_rate.confidence,
        "instructions": result.instructions.confidence,
        "overall": result.overall_confidence,
        "low_confidence_fields": result.low_confidence_fields,
    }
    invoice.extraction_model = result.model_id
    invoice.input_tokens = result.input_tokens
    invoice.output_tokens = result.output_tokens
    prev_status = invoice.status.value

    # ── Trinn 2: post-ekstraksjon null-felt-sjekk ─────────────────────────────
    empty, rejection_reason = _is_empty_extraction(invoice, result)
    if empty:
        invoice.status = InvoiceStatus.NOT_INVOICE
        invoice.extraction_error = rejection_reason
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="extracting",
            action="rejected",
            status_from=prev_status,
            status_to=InvoiceStatus.NOT_INVOICE.value,
            message=rejection_reason,
            payload={
                "reason": "not_invoice_post_extraction",
                "overall_confidence": result.overall_confidence,
                "model": result.model_id,
            },
        )
        await audit_service.log(
            session,
            action="invoice.rejected_not_invoice",
            invoice_id=invoice.id,
            details={
                "reason": rejection_reason,
                "stage": "post_extraction",
                "overall_confidence": result.overall_confidence,
                "model": result.model_id,
            },
        )
        await session.commit()
        await session.refresh(invoice)
        logger.info(
            "invoice_rejected_not_invoice",
            invoice_id=str(invoice.id),
            stage="post_extraction",
            overall_confidence=result.overall_confidence,
        )
        return  # stopp pipeline — ikke gå videre til screening

    invoice.status = InvoiceStatus.EXTRACTED

    # Slett eksisterende linjer og entities — re-ekstraksjon erstatter dem
    for line in list(invoice.lines):
        await session.delete(line)
    for entity in list(invoice.entities):
        await session.delete(entity)
    await session.flush()

    # Opprett nye linjer
    for i, extracted_line in enumerate(result.lines):
        line = InvoiceLine(
            invoice_id=invoice.id,
            line_number=i + 1,
            description=extracted_line.description,
            product_code=extracted_line.product_code,
            hs_code=extracted_line.hs_code,
            eccn=extracted_line.eccn,
            serial_number=extracted_line.serial_number,
            model_number=extracted_line.model_number,
            country_of_origin=extracted_line.country_of_origin,
            quantity=_to_decimal(extracted_line.quantity),
            unit_of_measure=extracted_line.unit_of_measure,
            unit_price=_to_decimal(extracted_line.unit_price),
            total_price=_to_decimal(extracted_line.total_price),
            currency=extracted_line.currency[:3].upper() if extracted_line.currency else None,
        )
        session.add(line)

    # Opprett nye entities
    for extracted_entity in result.entities:
        role = _map_role(extracted_entity.role)
        entity_type = _map_entity_type(extracted_entity.entity_type)
        entity = Entity(
            invoice_id=invoice.id,
            name=extracted_entity.name,
            entity_type=entity_type,
            country=extracted_entity.country,
            role=role,
            address=extracted_entity.address,
            phone=extracted_entity.phone,
            email=extracted_entity.email,
            confidence=getattr(extracted_entity, "confidence", None),
        )
        session.add(entity)

    await session.flush()
    updated_invoice = await get_invoice(session, invoice.id)
    apply_invoice_notes(updated_invoice)
    await append_pipeline_event(
        session,
        invoice_id=invoice.id,
        stage="extracting",
        action="completed",
        status_from=prev_status,
        status_to=InvoiceStatus.EXTRACTED.value,
        payload={
            "overall_confidence": result.overall_confidence,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "line_count": len(result.lines),
            "entity_count": len(result.entities),
            "model": result.model_id,
        },
    )
    await audit_service.log(
        session,
        action="extraction.completed",
        invoice_id=invoice.id,
        details={
            "model": result.model_id,
            "overall_confidence": result.overall_confidence,
            "low_confidence_fields": result.low_confidence_fields,
            "line_count": len(result.lines),
            "entity_count": len(result.entities),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
    )

    await session.commit()
    await session.refresh(invoice)


def _is_empty_extraction(invoice: Invoice, result: InvoiceExtractionResult) -> tuple[bool, str]:
    """Trinn 2: sjekk om ekstraksjon ga tilnærmet ingen data.

    Avviser dokumentet som «ikke faktura» dersom ≥ 3 av 4 kritiske felt
    mangler OG samlet konfidens er under 25 %.

    Returns:
        (True, grunn)  → bør avvises som not_invoice
        (False, "")    → ser ut som en faktura, fortsett
    """
    critical_null = sum(
        [
            invoice.invoice_number is None,
            invoice.total_amount is None,
            invoice.currency is None,
            invoice.invoice_date is None,
        ]
    )
    overall = result.overall_confidence or 0.0

    if critical_null >= 3 and overall < 0.25:
        return True, (
            f"LLM-ekstraksjon fant nesten ingen fakturadata "
            f"({critical_null}/4 nøkkelfelt mangler, konfidens {overall:.0%}). "
            "Dokumentet er sannsynligvis ikke en faktura."
        )
    return False, ""


def _to_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        cleaned = value.replace(",", ".").replace(" ", "").replace("\xa0", "")
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _map_role(role_str: str) -> EntityRole:
    try:
        return EntityRole(role_str.lower())
    except ValueError:
        return EntityRole.OTHER


def _map_entity_type(type_str: str) -> EntityType:
    try:
        return EntityType(type_str.lower())
    except ValueError:
        return EntityType.COMPANY
