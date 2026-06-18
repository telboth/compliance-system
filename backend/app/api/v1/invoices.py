"""Invoice-endepunkter."""

from __future__ import annotations

import csv
import io
import mimetypes
import re
import uuid
from datetime import date
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, Response

from app.core.config import get_settings
from app.core.database import SessionDep
from app.core.logging import get_logger
from app.core.security import ActorContext, require_roles
from app.models.invoice import (
    ComplianceScore,
    Invoice,
    InvoiceDirection,
    InvoiceStatus,
    compute_approval_state,
)
from app.schemas.invoice import (
    EntityRead,
    EntityUpdate,
    ExtractionRequest,
    ExtractionResponse,
    InvoiceFieldsUpdate,
    InvoiceLineRead,
    InvoiceLineUpdate,
    InvoiceListPreferences,
    InvoiceListPreferencesUpdate,
    InvoiceListResponse,
    InvoiceRead,
    InvoiceSummary,
    InvoiceUploadResponse,
    ReviewAndNextResponse,
    ReviewCreate,
    ReviewQueueResponse,
    RiskEscalationCreate,
    VatMismatchItem,
    VatMismatchListResponse,
)
from app.services import (
    extraction_service,
    invoice_preferences_service,
    invoice_review_service,
    invoice_service,
)
from app.services.catch_all_service import evaluate_invoice_catch_all
from app.services.export_control_service import evaluate_invoice_export_control
from app.services.vat_check_service import evaluate_invoice_vat_mismatch, list_vat_mismatch_invoices

router = APIRouter()
logger = get_logger(__name__)


def _parse_date(s: str | None) -> date | None:
    """Konverter ISO-dato-streng til date, eller None ved feil/tom verdi."""
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


# V7: Fjern kontrollkarakterer og anførselstegn som kan brekke Content-Disposition-headeren.
_CONTENT_DISPOSITION_UNSAFE = re.compile(r'[\x00-\x1f\x7f"\\]')


def _safe_filename(name: str) -> str:
    """Sanitér filnavn for bruk i Content-Disposition-header (RFC 6266).

    Erstatter tegn som kan forårsake header-splitting eller header-injection
    med understrek. Sikrer at resultatet aldri er tomt.
    """
    sanitized = _CONTENT_DISPOSITION_UNSAFE.sub("_", name).strip()
    return sanitized or "file"


def _to_invoice_read(invoice: Invoice) -> InvoiceRead:
    payload = InvoiceRead.model_validate(invoice)
    payload.vat_mismatch_check = evaluate_invoice_vat_mismatch(invoice).to_dict()
    payload.export_control_check = evaluate_invoice_export_control(invoice).to_dict()
    payload.catch_all_check = evaluate_invoice_catch_all(invoice).to_dict()
    payload.approval_state = (
        invoice.approval_state
        if invoice.approval_state is not None
        else compute_approval_state(invoice.status, invoice.compliance_score)
    )
    return payload


def _to_invoice_summary(inv: Invoice) -> InvoiceSummary:
    payload = InvoiceSummary.model_validate(inv)
    payload.approval_state = (
        inv.approval_state
        if inv.approval_state is not None
        else compute_approval_state(inv.status, inv.compliance_score)
    )
    payload.llm_note_full = inv.comments
    return payload


@router.post(
    "/upload",
    response_model=InvoiceUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Last opp en invoice (PDF, XLSX, PNG, JPG eller GIF)",
)
async def upload_invoice(
    background_tasks: BackgroundTasks,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
    file: UploadFile = File(..., description="PDF, XLSX, PNG, JPG/JPEG eller GIF med invoice"),
    direction: InvoiceDirection = Form(
        InvoiceDirection.INCOMING,
        description="Innkommende (kjøp) eller utgående (salg) faktura.",
    ),
    customer_id: uuid.UUID | None = Form(
        default=None,
        description="Koble invoicen til en eksisterende kunde (valgfritt).",
    ),
) -> InvoiceUploadResponse:
    """Lagrer filen og returnerer umiddelbart (status=uploaded).

    Docling-parsing starter i bakgrunnen — status oppdateres til 'parsing'
    og deretter 'parsed' (eller 'parsing_failed') når den er ferdig.
    Frontend poller GET /invoices/{id} til status er ferdig.

    Hvis auto-ekstraksjon er aktivert i settings, starter LLM-ekstraksjon
    automatisk etter vellykket parsing.
    """
    invoice, duplicate_detected = await invoice_service.upload_invoice_only(
        session=session,
        upload=file,
        direction=direction,
        customer_id=customer_id,
    )
    if duplicate_detected:
        return InvoiceUploadResponse(
            invoice=_to_invoice_read(invoice),
            duplicate_detected=True,
            duplicate_of_invoice_id=invoice.id,
        )

    settings = get_settings()
    if settings.use_celery_background:
        try:
            from app.tasks.process_invoice import run as process_invoice_task

            process_invoice_task.delay(str(invoice.id), str(Path(invoice.pdf_path)))
        except Exception:
            logger.exception(
                "celery_enqueue_parse_failed_fallback_background",
                invoice_id=str(invoice.id),
            )
            background_tasks.add_task(
                invoice_service.parse_invoice_in_background,
                invoice.id,
                Path(invoice.pdf_path),
                engine=session.bind,
            )
    else:
        background_tasks.add_task(
            invoice_service.parse_invoice_in_background,
            invoice.id,
            Path(invoice.pdf_path),
            engine=session.bind,
        )
    return InvoiceUploadResponse(invoice=_to_invoice_read(invoice))


@router.post(
    "/{invoice_id}/extract",
    response_model=ExtractionResponse,
    summary="Ekstraher strukturerte felter med LLM",
)
async def extract_invoice_endpoint(
    invoice_id: uuid.UUID,
    body: ExtractionRequest,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> ExtractionResponse:
    """Kjør LLM-ekstraksjon på en allerede parsert invoice.

    Returnerer oppdatert invoice med ekstraherte felter og konfidensscore.
    Felt med konfidens under terskelen listes i low_confidence_fields.
    """
    invoice, result = await extraction_service.run_extraction(
        session=session,
        invoice_id=invoice_id,
        model_id=body.model_id,
    )
    return ExtractionResponse(
        invoice=_to_invoice_read(invoice),
        overall_confidence=result.overall_confidence,
        low_confidence_fields=result.low_confidence_fields,
        model_id=result.model_id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


@router.patch(
    "/{invoice_id}/fields",
    response_model=InvoiceRead,
    summary="Korriger headerfelt manuelt",
)
async def update_invoice_fields_endpoint(
    invoice_id: uuid.UUID,
    body: InvoiceFieldsUpdate,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> InvoiceRead:
    """Oppdater ett eller flere headerfelt på en invoice manuelt.

    Kun felt som er angitt i request-body oppdateres — de andre røres ikke.
    Brukes til å korrigere feil fra LLM-ekstraksjon.
    """
    invoice = await invoice_service.update_invoice_fields(session, invoice_id, body)
    return _to_invoice_read(invoice)


@router.patch(
    "/{invoice_id}/lines/{line_id}",
    response_model=InvoiceLineRead,
    summary="Korriger en invoice-linje manuelt",
)
async def update_invoice_line_endpoint(
    invoice_id: uuid.UUID,
    line_id: uuid.UUID,
    body: InvoiceLineUpdate,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> InvoiceLineRead:
    """Oppdater ett eller flere felt på en enkelt invoice-linje manuelt."""
    line = await invoice_service.update_invoice_line(session, invoice_id, line_id, body)
    return InvoiceLineRead.model_validate(line)


@router.patch(
    "/{invoice_id}/entities/{entity_id}",
    response_model=EntityRead,
    summary="Korriger en entitet manuelt",
)
async def update_entity_endpoint(
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: EntityUpdate,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> EntityRead:
    """Oppdater ett eller flere felt på en entitet manuelt."""
    entity = await invoice_service.update_entity(session, invoice_id, entity_id, body)
    return EntityRead.model_validate(entity)


@router.post(
    "/{invoice_id}/reparse",
    response_model=InvoiceRead,
    summary="Re-parser en invoice med Docling (nyttig etter parsing-forbedringer)",
)
async def reparse_invoice_endpoint(
    invoice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> InvoiceRead:
    """Nullstill raw_text og kjør Docling-parsing på nytt i bakgrunnen.

    Brukes etter forbedringer i parsing-pipelinen uten å måtte laste opp filen på nytt.
    Status settes til 'parsing' umiddelbart; frontend poller til 'parsed'.
    """
    invoice = await invoice_service.get_invoice(session, invoice_id)
    invoice.status = InvoiceStatus.UPLOADED  # tvinger re-parsing
    invoice.raw_text = None
    invoice.parsing_error = None
    await session.commit()
    await session.refresh(invoice)

    settings = get_settings()
    if settings.use_celery_background:
        try:
            from app.tasks.process_invoice import run as process_invoice_task

            process_invoice_task.delay(str(invoice.id), str(Path(invoice.pdf_path)))
        except Exception:
            logger.exception(
                "celery_enqueue_reparse_failed_fallback_background",
                invoice_id=str(invoice.id),
            )
            background_tasks.add_task(
                invoice_service.parse_invoice_in_background,
                invoice.id,
                Path(invoice.pdf_path),
                engine=session.bind,
            )
    else:
        background_tasks.add_task(
            invoice_service.parse_invoice_in_background,
            invoice.id,
            Path(invoice.pdf_path),
            engine=session.bind,
        )
    return _to_invoice_read(invoice)


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Slett en invoice og tilhørende filer",
)
async def delete_invoice_endpoint(
    invoice_id: uuid.UUID,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin")),
) -> Response:
    """Slett en invoice permanent (inkl. fil på disk og alle linjer/entiteter).

    Kun tilgjengelig for admin — sletting fjerner også audit-loggen for facturaen.
    """
    await invoice_service.delete_invoice(session, invoice_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{invoice_id}/file",
    summary="Hent originalfil for en invoice (PDF, PNG eller XLSX)",
)
async def get_invoice_file(
    invoice_id: uuid.UUID,
    session: SessionDep,
) -> FileResponse:
    """Returnerer originalfilen inline — PDF og PNG vises direkte i nettleseren,
    XLSX lastes ned automatisk.
    """
    invoice = await invoice_service.get_invoice(session, invoice_id)
    file_path = Path(invoice.pdf_path)

    # Path traversal-vern: filen må ligge under upload-katalogen.
    # resolve() og exists() er rene minneoperasjoner på allerede kjente stier
    # (ingen nettverks-I/O).
    upload_dir = get_settings().upload_dir.resolve()
    try:
        resolved = file_path.resolve()
        if not resolved.is_relative_to(upload_dir):
            raise HTTPException(status_code=403, detail="Tilgang nektet.")
    except ValueError:
        raise HTTPException(status_code=403, detail="Tilgang nektet.") from None

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Filen finnes ikke på disk.")

    original_name = _safe_filename(invoice.original_filename or file_path.name)
    media_type, _ = mimetypes.guess_type(original_name)

    return FileResponse(
        path=str(file_path),
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{original_name}"'},
    )


@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="List invoices med paginering og filtrering",
)
async def list_invoices_endpoint(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: InvoiceStatus | None = Query(None, alias="status"),
    direction: InvoiceDirection | None = Query(None, description="Filtrer på innkommende/utgående"),
    compliance_score: ComplianceScore | None = Query(
        None, description="Filtrer på compliance-resultat (green/yellow/red)"
    ),
    vat_note_status: str | None = Query(
        None,
        description="Filtrer på moms-merknad status (ok/warn/error).",
        pattern="^(ok|warn|error)$",
    ),
    email_note_status: str | None = Query(
        None,
        description="Filtrer på epost-merknad status (ok/warn/error).",
        pattern="^(ok|warn|error)$",
    ),
    approval_state: str | None = Query(
        None,
        description="Filtrer på godkjenningsstatus (pending/approved/blocked/not_required/assessing).",
        pattern="^(pending|approved|blocked|not_required|assessing)$",
    ),
    destination_country: str | None = Query(None, description="ISO-landkode (f.eks. RU, DE)"),
    date_from: str | None = Query(None, description="Fakturadato fra og med (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Fakturadato til og med (YYYY-MM-DD)"),
    sort_by: str | None = Query(
        "created_at",
        description=(
            "Sorter på felt: created_at, invoice_date, total_amount, status, "
            "compliance_score, approval_state, vat_note_status, email_note_status, "
            "llm_note_preview, original_filename."
        ),
    ),
    sort_dir: str = Query(
        "desc",
        pattern="^(asc|desc)$",
        description="Sorteringsretning.",
    ),
) -> InvoiceListResponse:
    invoices, total = await invoice_service.list_invoices(
        session,
        limit=limit,
        offset=offset,
        status=status_filter,
        direction=direction,
        compliance_score=compliance_score,
        vat_note_status=vat_note_status,
        email_note_status=email_note_status,
        approval_state=approval_state,
        destination_country=destination_country,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    items = [_to_invoice_summary(inv) for inv in invoices]
    return InvoiceListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/preferences/invoice-list",
    response_model=InvoiceListPreferences,
    summary="Hent lagrede kolonne-/filterpreferanser for bruker",
)
async def get_invoice_list_preferences_endpoint(
    session: SessionDep,
    actor_ctx: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller", "readonly")),
) -> InvoiceListPreferences:
    payload, updated_at = await invoice_preferences_service.get_invoice_list_preferences(
        session,
        actor_name=actor_ctx.name,
    )
    return InvoiceListPreferences(
        table_col_widths=payload.get("table_col_widths") or {},
        table_col_presets=payload.get("table_col_presets") or [],
        default_filters=payload.get("default_filters") or {},
        updated_at=updated_at,
    )


@router.put(
    "/preferences/invoice-list",
    response_model=InvoiceListPreferences,
    summary="Lagre kolonne-/filterpreferanser for bruker",
)
async def update_invoice_list_preferences_endpoint(
    body: InvoiceListPreferencesUpdate,
    session: SessionDep,
    actor_ctx: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller", "readonly")),
) -> InvoiceListPreferences:
    payload, updated_at = await invoice_preferences_service.update_invoice_list_preferences(
        session,
        actor_name=actor_ctx.name,
        update=body,
    )
    return InvoiceListPreferences(
        table_col_widths=payload.get("table_col_widths") or {},
        table_col_presets=payload.get("table_col_presets") or [],
        default_filters=payload.get("default_filters") or {},
        updated_at=updated_at,
    )


@router.get(
    "/export",
    summary="Eksporter fakturaliste som CSV",
)
async def export_invoices_csv(
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
    status_filter: InvoiceStatus | None = Query(None, alias="status"),
    direction: InvoiceDirection | None = Query(None),
    compliance_score: ComplianceScore | None = Query(None),
    destination_country: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
) -> Response:
    """Last ned fakturalisten som CSV-fil med aktive filtre.

    Maks 5000 rader per eksport.
    """
    invoices, _ = await invoice_service.list_invoices(
        session,
        limit=5000,
        offset=0,
        status=status_filter,
        direction=direction,
        compliance_score=compliance_score,
        destination_country=destination_country,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        sort_by="created_at",
        sort_dir="desc",
    )

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        [
            "Fakturanummer",
            "Filnavn",
            "Retning",
            "Status",
            "Compliance-score",
            "Beløp",
            "Valuta",
            "Fakturadato",
            "Destinasjonsland",
            "Beslutning",
            "Besluttet av",
            "Besluttet tidspunkt",
            "Opprettet",
        ]
    )
    for inv in invoices:
        writer.writerow(
            [
                inv.invoice_number or "",
                inv.original_filename or "",
                inv.direction.value,
                inv.status.value,
                inv.compliance_score.value if inv.compliance_score else "",
                str(inv.total_amount) if inv.total_amount else "",
                inv.currency or "",
                inv.invoice_date.isoformat() if inv.invoice_date else "",
                inv.destination_country or "",
                inv.review_decision or "",
                inv.reviewed_by or "",
                inv.reviewed_at.isoformat() if inv.reviewed_at else "",
                inv.created_at.isoformat(),
            ]
        )

    filename = f"fakturaer-{date.today().isoformat()}.csv"
    return Response(
        content="﻿" + buf.getvalue(),  # BOM for Excel-kompatibilitet
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/vat-mismatches",
    response_model=VatMismatchListResponse,
    summary="Sjekk mulig feilregistrert VAT pa tvers av invoices",
)
async def list_vat_mismatches_endpoint(
    session: SessionDep,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    flagged_only: bool = Query(
        True,
        description="True = returner kun invoices som er flagget av VAT-regelen.",
    ),
) -> VatMismatchListResponse:
    items, total_flagged, total_scanned = await list_vat_mismatch_invoices(
        session,
        limit=limit,
        offset=offset,
        flagged_only=flagged_only,
    )
    return VatMismatchListResponse(
        total_scanned=total_scanned,
        total_flagged=total_flagged,
        limit=limit,
        offset=offset,
        items=[
            VatMismatchItem(
                invoice_id=item.invoice.id,
                invoice_number=item.invoice.invoice_number,
                original_filename=item.invoice.original_filename,
                direction=item.invoice.direction,
                status=item.invoice.status,
                invoice_date=item.invoice.invoice_date,
                created_at=item.invoice.created_at,
                vat_check=item.check.to_dict(),
            )
            for item in items
        ],
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceRead,
    summary="Hent en spesifikk invoice",
)
async def get_invoice_endpoint(
    invoice_id: uuid.UUID,
    session: SessionDep,
) -> InvoiceRead:
    invoice = await invoice_service.get_invoice(session, invoice_id)
    return _to_invoice_read(invoice)


@router.post(
    "/{invoice_id}/review",
    response_model=InvoiceRead,
    summary="Godkjenn eller blokker en invoice (manuell review)",
)
async def review_invoice_endpoint(
    invoice_id: uuid.UUID,
    body: ReviewCreate,
    session: SessionDep,
    actor_ctx: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> InvoiceRead:
    """Sett en manuell beslutning på en screenet invoice.

    - **decision**: `approved` eller `blocked`
    - **reason**: Obligatorisk begrunnelse (min. 10 tegn)
    """
    try:
        invoice = await invoice_review_service.review_invoice(
            session,
            invoice_id,
            decision=body.decision,
            reason=body.reason,
            rule_reference=body.rule_reference,
            evidence_summary=body.evidence_summary,
            deviation_approval=body.deviation_approval,
            actor=actor_ctx.name,
        )
    except invoice_review_service.ReviewClaimConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    return _to_invoice_read(invoice)


@router.post(
    "/{invoice_id}/review-and-next",
    response_model=ReviewAndNextResponse,
    summary="Godkjenn/blokker invoice og hent neste sak atomisk",
)
async def review_invoice_and_next_endpoint(
    invoice_id: uuid.UUID,
    body: ReviewCreate,
    session: SessionDep,
    actor_ctx: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> ReviewAndNextResponse:
    settings = get_settings()
    try:
        invoice, next_invoice_id = await invoice_review_service.review_invoice_and_next(
            session,
            invoice_id,
            decision=body.decision,
            reason=body.reason,
            rule_reference=body.rule_reference,
            evidence_summary=body.evidence_summary,
            deviation_approval=body.deviation_approval,
            actor=actor_ctx.name,
            stale_minutes=settings.review_claim_stale_minutes,
        )
    except invoice_review_service.ReviewClaimConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    return ReviewAndNextResponse(
        invoice=_to_invoice_read(invoice),
        next_invoice_id=next_invoice_id,
    )


@router.post(
    "/{invoice_id}/claim",
    response_model=InvoiceRead,
    summary="Claim en invoice i review-køen",
)
async def claim_review_invoice_endpoint(
    invoice_id: uuid.UUID,
    session: SessionDep,
    actor_ctx: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> InvoiceRead:
    settings = get_settings()
    try:
        invoice = await invoice_review_service.claim_review_invoice(
            session,
            invoice_id,
            actor=actor_ctx.name,
            stale_minutes=settings.review_claim_stale_minutes,
        )
    except invoice_review_service.ReviewClaimConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    return _to_invoice_read(invoice)


@router.delete(
    "/{invoice_id}/claim",
    response_model=InvoiceRead,
    summary="Frigi claim på en invoice",
)
async def release_review_claim_endpoint(
    invoice_id: uuid.UUID,
    session: SessionDep,
    actor_ctx: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> InvoiceRead:
    settings = get_settings()
    try:
        invoice = await invoice_review_service.release_review_claim(
            session,
            invoice_id,
            actor=actor_ctx.name,
            stale_minutes=settings.review_claim_stale_minutes,
        )
    except invoice_review_service.ReviewClaimConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.message,
        ) from exc
    return _to_invoice_read(invoice)


@router.post(
    "/{invoice_id}/risk/escalate",
    response_model=InvoiceRead,
    summary="Eskalér grønn invoice til gul/rød for manuell review",
)
async def escalate_invoice_risk_endpoint(
    invoice_id: uuid.UUID,
    body: RiskEscalationCreate,
    session: SessionDep,
    actor_ctx: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> InvoiceRead:
    """La controller eskalere en grønn invoice til gul/rød ved manuell observasjon.

    Eskalering setter status til 'screened' og nullstiller tidligere review-beslutning,
    slik at compliance/admin må godkjenne eller blokkere på nytt.
    """
    target = ComplianceScore(body.target_score)
    invoice = await invoice_service.escalate_invoice_risk_for_review(
        session,
        invoice_id,
        target_score=target,
        reason=body.reason,
        actor=actor_ctx.name,
    )
    return _to_invoice_read(invoice)


@router.get(
    "/queue/review",
    response_model=ReviewQueueResponse,
    summary="Hent fakturaer som venter på review",
)
async def get_review_queue(
    session: SessionDep,
    actor_ctx: ActorContext = Depends(require_roles("admin", "compliance_officer")),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    score: ComplianceScore | None = Query(default=None, description="Filtrer på compliance_score"),
) -> ReviewQueueResponse:
    """Returnerer compliance-kø sortert: høyeste risiko først, deretter eldste først."""
    return await invoice_review_service.list_review_queue(
        session,
        actor_name=actor_ctx.name,
        limit=limit,
        offset=offset,
        score=score,
    )
