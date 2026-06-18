"""Sanksjonsscreening-endepunkter.

To routere eksporteres:
  invoice_router    — per-invoice, monteres under /invoices
  admin_router      — yente-administrasjon, monteres under /sanctions

invoice_router:
  POST /{invoice_id}/screen       — Start screening
  GET  /{invoice_id}/screening    — Hent resultater

admin_router:
  GET  /status     — Yente-status og datasett-oversikt
  POST /refresh    — Trigger manuell reindeksering
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.core.config import get_settings
from app.core.database import SessionDep
from app.core.logging import get_logger
from app.core.security import ActorContext, require_roles
from app.models.entity import Entity
from app.models.invoice import Invoice, InvoiceStatus
from app.models.screening import MatchStatus, ScreeningResult
from app.sanctions.yente_client import YenteMatch, get_yente_client
from app.schemas.screening import (
    AdHocScreenEntityResult,
    AdHocScreenMatch,
    AdHocScreenRequest,
    AdHocScreenResponse,
    ExtendedScreenClaimRead,
    ExtendedScreenFeedbackCreate,
    ExtendedScreenFeedbackRead,
    ExtendedScreenRunRead,
    ExtendedScreenRunResponse,
    ExtendedScreenSourceRead,
    ExtendedScreenStartRequest,
    ExternalSourceHealthStatus,
    LocalSanctionsSourceStatus,
    PipelineMetricsResponse,
    PipelineRecoveryActionResponse,
    PipelineRecoveryResponse,
    SanctionedEntityListResponse,
    SanctionedEntityRead,
    SanctionsRefreshResponse,
    SanctionsRefreshRunStatus,
    SanctionsStatusResponse,
    ScreeningCandidateDebugRead,
    ScreeningCandidatesResponse,
    ScreeningResultRead,
    ScreeningResultsResponse,
    YenteDatasetStatus,
)
from app.services import screening_service
from app.services.extended_screening_service import (
    add_extended_screen_feedback,
    create_extended_screen_run,
    execute_extended_screen_run,
    get_extended_screen_run,
    list_extended_screen_claims,
    list_extended_screen_feedback,
    list_extended_screen_sources,
)
from app.services.external_watchlist_service import (
    list_external_source_health,
    run_external_watchlist_ingest_cycle,
)
from app.services.invoice_service import get_invoice
from app.services.pipeline_event_service import append_pipeline_event
from app.services.pipeline_ops_service import (
    get_invoice_for_recovery,
    get_pipeline_metrics,
    list_pipeline_recovery_candidates,
)
from app.services.sanctions_loader_service import list_local_sanctions_statuses
from app.services.sanctions_refresh_service import (
    get_latest_refresh_run,
    run_sanctions_refresh_cycle_with_trigger,
)

logger = get_logger(__name__)

invoice_router = APIRouter()
admin_router = APIRouter()
public_router = APIRouter()

# Behold "router" som alias for invoice_router for bakoverkompatibilitet
router = invoice_router
_SCREENING_STALE_AFTER = timedelta(minutes=3)


async def _elasticsearch_status() -> tuple[bool, str | None]:
    """Returner (tilgjengelig, feilmelding) for Elasticsearch."""
    settings = get_settings()
    base_url = settings.elasticsearch_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/_cluster/health")
            response.raise_for_status()
        return True, None
    except Exception as exc:
        return False, str(exc)


_COMPANY_OR_PERSON_SCHEMAS = {
    "person",
    "legalentity",
    "organization",
    "company",
}


def _classify_score(score: float, confirmed: float, potential: float) -> str:
    if score >= confirmed:
        return "confirmed_match"
    if score >= potential:
        return "potential_match"
    return "clear"


def _to_ad_hoc_match(match: YenteMatch) -> AdHocScreenMatch:
    sanctions_type = None
    if match.raw:
        topics = (match.raw.get("properties", {}) or {}).get("topics", [])
        if isinstance(topics, list) and topics:
            sanctions_type = str(topics[0])

    return AdHocScreenMatch(
        list=match.dataset,
        score=match.score,
        matched_name=match.matched_name,
        sanctions_type=sanctions_type,
    )


def _get_payload_str(payload: dict[str, Any], key: str) -> str | None:
    """Returner trimmet strengverdi fra payload dersom den finnes."""
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_match_explanation(
    *,
    dataset: str,
    matched_name: str | None,
    raw_response: dict[str, Any] | None,
    entity_name: str | None,
) -> str | None:
    """Bygg menneskelesbar forklaring pa hvorfor en rad fikk treff."""
    if not raw_response:
        if matched_name:
            return f"Treff mot sanksjonert navn '{matched_name}' i datasett '{dataset}'."
        return None

    check_type = _get_payload_str(raw_response, "check_type")
    if check_type == "country_embargo":
        scope = _get_payload_str(raw_response, "scope")
        country_name = _get_payload_str(raw_response, "matched_name") or matched_name
        if scope == "comprehensive":
            return f"Landembargo: '{country_name or 'ukjent land'}' er markert som comprehensive embargo."
        if scope == "sectoral":
            return f"Landembargo: '{country_name or 'ukjent land'}' har sectoral embargo (potensielt treff)."
        return f"Landembargo-treff mot '{country_name or 'ukjent land'}'."
    if check_type == "trade_plausibility_industry_mismatch":
        return (
            "Handelsplausibilitet: vareinnhold ser uvanlig ut i forhold til oppgitt "
            "kjoper/bransje og rute. Bør vurderes manuelt."
        )
    if check_type == "trade_plausibility_free_zone_transit":
        return (
            "Handelsplausibilitet: frihandelssone/transittmønster med industrivarer "
            "kan indikere omgaelsesrisiko. Bør vurderes manuelt."
        )
    if check_type == "duplicate_invoice_similarity":
        matched_invoice = _get_payload_str(raw_response, "matched_invoice_number")
        matched_file = _get_payload_str(raw_response, "matched_filename")
        label = matched_invoice or matched_file or "tidligere faktura"
        return f"Mulig duplikat: høy likhet mot {label} (navn/beløp/tekst/fakturanummer)."

    query_source = _get_payload_str(raw_response, "query_source")
    query_name = _get_payload_str(raw_response, "query_name")
    query_email = _get_payload_str(raw_response, "query_email")
    effective_match = matched_name or _get_payload_str(raw_response, "matched_name")

    if query_source == "raw_text_email":
        if query_email and query_name and effective_match:
            return (
                f"Treff fra e-post i dokumenttekst '{query_email}'. "
                f"Ekstrahert navn '{query_name}' matchet mot '{effective_match}'."
            )
        if query_email and query_name:
            return (
                f"Treff fra e-post i dokumenttekst '{query_email}'. "
                f"Ekstrahert navn '{query_name}' ga match i sanksjonsliste."
            )
        if query_name:
            return f"Treff fra e-post i dokumenttekst, soketerm '{query_name}'."

    if query_source == "raw_text_label":
        if query_name and effective_match:
            return f"Treff fra dokumenttekst (label/overskrift): '{query_name}' matchet mot '{effective_match}'."
        if query_name:
            return f"Treff fra dokumenttekst (label/overskrift), soketerm '{query_name}'."

    if query_source == "entity_email":
        if query_email and query_name and effective_match:
            return (
                f"Treff fra e-post pa entitet '{entity_name or 'ukjent entitet'}' "
                f"({query_email}). Ekstrahert navn '{query_name}' matchet mot "
                f"'{effective_match}'."
            )
        if query_email and query_name:
            return (
                f"Treff fra e-post pa entitet '{entity_name or 'ukjent entitet'}' "
                f"({query_email}), soketerm '{query_name}'."
            )
        if query_name:
            return (
                f"Treff fra e-postbasert sok for entitet "
                f"'{entity_name or 'ukjent entitet'}' med soketerm '{query_name}'."
            )

    if query_source == "entity_name":
        if query_name and effective_match:
            return f"Treff fra entitetsnavn '{query_name}' mot sanksjonert navn '{effective_match}'."
        if query_name:
            return f"Treff fra entitetsnavn '{query_name}'."

    if query_name and effective_match:
        return f"Soketerm '{query_name}' matchet mot '{effective_match}'."
    if query_name:
        return f"Soketerm '{query_name}' ga treff i sanksjonsliste."
    if effective_match:
        return f"Treff mot sanksjonert navn '{effective_match}'."
    return None


def _screening_identity(result: ScreeningResult) -> tuple[str, str, str, str, str]:
    """Semantisk noekkel for deduplisering av screeningrader."""
    return (
        str(result.entity_id),
        result.dataset,
        result.dataset_entity_id or "",
        (result.matched_name or "").strip().lower(),
        result.status.value,
    )


def _dedupe_screening_rows(results: list[ScreeningResult]) -> list[ScreeningResult]:
    """Fjern duplikatrader og behold sterkeste/nyeste variant per treff."""
    by_key: dict[tuple[str, str, str, str, str], ScreeningResult] = {}
    for row in results:
        key = _screening_identity(row)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = row
            continue

        keep_new = row.score > existing.score or (
            row.score == existing.score and row.screened_at > existing.screened_at
        )
        if keep_new:
            by_key[key] = row

    deduped = sorted(
        by_key.values(),
        key=lambda row: (row.screened_at, row.score),
        reverse=True,
    )
    removed = len(results) - len(deduped)
    if removed > 0:
        logger.warning(
            "screening_duplicates_removed",
            original=len(results),
            deduped=len(deduped),
            removed=removed,
        )
    return deduped


# ── Per-invoice screening ─────────────────────────────────────────────────────


@public_router.post(
    "/screen",
    response_model=AdHocScreenResponse,
    summary="Screen entiteter mot sanksjonslister",
)
async def ad_hoc_screen_entities(
    body: AdHocScreenRequest,
) -> AdHocScreenResponse:
    """Ad hoc screening uten å opprette invoice."""
    yente = get_yente_client()
    if not await yente.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Yente-tjenesten er ikke tilgjengelig.",
        )

    settings = get_settings()
    confirmed_threshold = float(settings.screening_confirmed_threshold)
    potential_threshold = float(settings.screening_match_threshold)

    payload = [
        {
            "id": str(idx),
            "name": entity.name,
            "entity_type": entity.entity_type,
            "country": entity.country,
        }
        for idx, entity in enumerate(body.entities)
    ]
    batch = await yente.match_entities_batch(payload)

    results: list[AdHocScreenEntityResult] = []
    for idx, entity in enumerate(body.entities):
        query_id = str(idx)
        matches = batch.get(query_id)
        if matches is None:
            results.append(
                AdHocScreenEntityResult(
                    entity=entity.name,
                    matches=[],
                    status="error",
                )
            )
            continue

        filtered = [m for m in matches if m.score >= potential_threshold]
        filtered.sort(key=lambda m: m.score, reverse=True)
        if not filtered:
            results.append(
                AdHocScreenEntityResult(
                    entity=entity.name,
                    matches=[],
                    status="clear",
                )
            )
            continue

        worst_status = max(
            (_classify_score(m.score, confirmed_threshold, potential_threshold) for m in filtered),
            key=lambda val: {"clear": 0, "potential_match": 1, "confirmed_match": 2}[val],
        )
        results.append(
            AdHocScreenEntityResult(
                entity=entity.name,
                matches=[_to_ad_hoc_match(match) for match in filtered],
                status="flagged" if worst_status != "clear" else "clear",
            )
        )

    return AdHocScreenResponse(results=results)


@invoice_router.post(
    "/{invoice_id}/screen",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start sanksjonsscreening",
    response_description="Screening er satt i ko — poll GET /{id}/screening for resultater.",
)
async def start_screening(
    invoice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> dict[str, str]:
    """Start sanksjonsscreening for en invoice asynkront.

    Returner 202 umiddelbart. Screeningen kjorer i bakgrunnen.
    Poll GET /invoices/{id} (status-felt) eller GET /invoices/{id}/screening
    for resultater.
    """
    invoice = await get_invoice(session, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} finnes ikke",
        )

    stale_screening = False
    if invoice.status == InvoiceStatus.SCREENING:
        now = datetime.now(UTC)
        updated_at = invoice.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        age = now - updated_at
        if age < _SCREENING_STALE_AFTER:
            return {
                "message": "Screening er allerede i gang",
                "invoice_id": str(invoice_id),
            }
        stale_screening = True
        logger.warning(
            "screening_marked_stale_requeue",
            invoice_id=str(invoice_id),
            stale_seconds=int(age.total_seconds()),
        )

    allowed_statuses = {
        InvoiceStatus.EXTRACTED,
        InvoiceStatus.SCREENED,
        InvoiceStatus.SCREENING_FAILED,
    }
    if stale_screening:
        allowed_statuses.add(InvoiceStatus.SCREENING)

    if invoice.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Invoice ma vaere i status 'extracted', 'screened' eller 'screening_failed' "
                f"for a kunne screenes. Na er status: {invoice.status.value!r}"
            ),
        )

    # Sett status umiddelbart slik at frontend viser at jobben er i gang.
    prev_status = invoice.status.value
    invoice.status = InvoiceStatus.SCREENING
    await append_pipeline_event(
        session,
        invoice_id=invoice.id,
        stage="screening",
        action="queued",
        status_from=prev_status,
        status_to=InvoiceStatus.SCREENING.value,
        message="Manual screen trigger queued.",
    )
    await session.commit()

    settings = get_settings()
    if settings.use_celery_background:
        try:
            from app.tasks.screen_entities import run as screen_entities_task

            screen_entities_task.delay(str(invoice_id))
        except Exception:
            logger.exception(
                "celery_enqueue_screen_failed_fallback_background",
                invoice_id=str(invoice_id),
            )
            background_tasks.add_task(
                _run_screening_background,
                invoice_id=invoice_id,
            )
    else:
        background_tasks.add_task(
            _run_screening_background,
            invoice_id=invoice_id,
        )

    return {"message": "Screening startet", "invoice_id": str(invoice_id)}


@invoice_router.post(
    "/{invoice_id}/entities/{entity_id}/extended-screen",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ExtendedScreenRunRead,
    summary="Start utvidet screening på én entitet",
)
async def start_extended_screening(
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: ExtendedScreenStartRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> ExtendedScreenRunRead:
    """Start MVP utvidet screening (nettverksdue-diligence) på en entitet."""
    try:
        run = await create_extended_screen_run(
            session,
            invoice_id=invoice_id,
            entity_id=entity_id,
            aggressiveness=body.aggressiveness,
            run_config={
                "min_edge_confidence": body.min_edge_confidence,
                "selected_only": body.selected_only,
                "sanctions_near_only": body.sanctions_near_only,
                "enable_brreg": body.enable_brreg,
                "enable_uk_sanctions": body.enable_uk_sanctions,
                "enable_world_bank_debarred": body.enable_world_bank_debarred,
                "enable_ai_entity_research": body.enable_ai_entity_research,
                "enable_ai_web_search": body.enable_ai_web_search,
            },
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    settings = get_settings()
    if settings.use_celery_background:
        try:
            from app.tasks.extended_screen import run as extended_screen_task

            extended_screen_task.delay(str(run.id))
        except Exception:
            logger.exception(
                "celery_enqueue_extended_screen_failed_fallback_background",
                run_id=str(run.id),
            )
            background_tasks.add_task(_run_extended_screen_background, run.id)
    else:
        background_tasks.add_task(_run_extended_screen_background, run.id)

    return ExtendedScreenRunRead.model_validate(run)


@invoice_router.get(
    "/{invoice_id}/entities/{entity_id}/extended-screen/{run_id}",
    response_model=ExtendedScreenRunResponse,
    summary="Hent status/resultat for utvidet screening",
)
async def get_extended_screening_status(
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
    session: SessionDep,
) -> ExtendedScreenRunResponse:
    """Hent status og MVP-resultat for én utvidet-screening-kjøring."""
    try:
        run = await get_extended_screen_run(
            session,
            invoice_id=invoice_id,
            entity_id=entity_id,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ExtendedScreenRunResponse.model_validate(run)


@invoice_router.post(
    "/{invoice_id}/entities/{entity_id}/extended-screen/{run_id}/feedback",
    response_model=ExtendedScreenFeedbackRead,
    summary="Lag analyst-feedback på utvidet screening",
)
async def create_extended_screen_feedback(
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
    body: ExtendedScreenFeedbackCreate,
    session: SessionDep,
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer", "controller")),
) -> ExtendedScreenFeedbackRead:
    try:
        row = await add_extended_screen_feedback(
            session,
            invoice_id=invoice_id,
            entity_id=entity_id,
            run_id=run_id,
            feedback_label=body.feedback_label,
            target_qid=body.target_qid,
            target_name=body.target_name,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return ExtendedScreenFeedbackRead.model_validate(row)


@invoice_router.get(
    "/{invoice_id}/entities/{entity_id}/extended-screen/{run_id}/feedback",
    response_model=list[ExtendedScreenFeedbackRead],
    summary="List analyst-feedback for utvidet screening",
)
async def get_extended_screen_feedback(
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
    session: SessionDep,
) -> list[ExtendedScreenFeedbackRead]:
    try:
        rows = await list_extended_screen_feedback(
            session,
            invoice_id=invoice_id,
            entity_id=entity_id,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [ExtendedScreenFeedbackRead.model_validate(row) for row in rows]


@invoice_router.get(
    "/{invoice_id}/entities/{entity_id}/extended-screen/{run_id}/sources",
    response_model=list[ExtendedScreenSourceRead],
    summary="List kilder brukt i utvidet screening",
)
async def get_extended_screen_sources(
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
    session: SessionDep,
) -> list[ExtendedScreenSourceRead]:
    try:
        rows = await list_extended_screen_sources(
            session,
            invoice_id=invoice_id,
            entity_id=entity_id,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [ExtendedScreenSourceRead.model_validate(row) for row in rows]


@invoice_router.get(
    "/{invoice_id}/entities/{entity_id}/extended-screen/{run_id}/claims",
    response_model=list[ExtendedScreenClaimRead],
    summary="List claims/evidens fra utvidet screening",
)
async def get_extended_screen_claims(
    invoice_id: uuid.UUID,
    entity_id: uuid.UUID,
    run_id: uuid.UUID,
    session: SessionDep,
) -> list[ExtendedScreenClaimRead]:
    try:
        rows = await list_extended_screen_claims(
            session,
            invoice_id=invoice_id,
            entity_id=entity_id,
            run_id=run_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return [ExtendedScreenClaimRead.model_validate(row) for row in rows]


async def _run_screening_background(invoice_id: uuid.UUID) -> None:
    """Hjelpefunksjon som kjoeres som BackgroundTask."""
    from app.core.database import get_session_factory
    from app.services.screening_service import ScreeningLockUnavailableError

    async with get_session_factory()() as session:
        try:
            await screening_service.screen_invoice(session, invoice_id)
        except ScreeningLockUnavailableError:
            logger.info(
                "background_screening_skipped_lock_conflict",
                invoice_id=str(invoice_id),
            )
        except Exception:
            logger.exception(
                "background_screening_failed",
                invoice_id=str(invoice_id),
            )


async def _run_extended_screen_background(run_id: uuid.UUID) -> None:
    """Hjelpefunksjon for lokal async-kjøring uten Celery."""
    await execute_extended_screen_run(run_id)


async def _run_extraction_background(invoice_id: uuid.UUID) -> None:
    """Kjør ekstraksjon asynkront i bakgrunnen (uten Celery)."""
    from app.core.database import get_session_factory
    from app.services.extraction_service import run_extraction

    async with get_session_factory()() as local_session:
        try:
            await run_extraction(local_session, invoice_id=invoice_id, model_id=None)
        except Exception:
            logger.exception("background_extraction_failed", invoice_id=str(invoice_id))


@invoice_router.get(
    "/{invoice_id}/screening",
    response_model=ScreeningResultsResponse,
    summary="Hent screeningresultater for en invoice",
)
async def get_screening_results(
    invoice_id: uuid.UUID,
    session: SessionDep,
) -> ScreeningResultsResponse:
    """Hent alle screeningresultater med entitetsnavn og kompliansestatus."""
    invoice = await get_invoice(session, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} finnes ikke",
        )

    raw_results = await screening_service.get_screening_results(session, invoice_id)
    deduped_results = _dedupe_screening_rows(raw_results)

    # Bygg et oppslags-dict for entiteter slik at vi kan denormalisere
    from sqlalchemy import select

    entity_result = await session.execute(select(Entity).where(Entity.invoice_id == invoice_id))
    entity_map = {str(e.id): e for e in entity_result.scalars().all()}

    result_reads: list[ScreeningResultRead] = []
    for r in deduped_results:
        entity = entity_map.get(str(r.entity_id))
        result_reads.append(
            ScreeningResultRead(
                id=r.id,
                invoice_id=r.invoice_id,
                entity_id=r.entity_id,
                dataset=r.dataset,
                dataset_entity_id=r.dataset_entity_id,
                matched_name=r.matched_name,
                score=r.score,
                listed_on=r.listed_on,
                status=r.status,
                screened_at=r.screened_at,
                entity_name=entity.name if entity else None,
                entity_role=entity.role.value if entity else None,
                match_explanation=_build_match_explanation(
                    dataset=r.dataset,
                    matched_name=r.matched_name,
                    raw_response=r.raw_response,
                    entity_name=entity.name if entity else None,
                ),
            )
        )

    # Finn nyeste screened_at
    screened_at: datetime | None = (
        max((r.screened_at for r in deduped_results), default=None) if deduped_results else None
    )

    confirmed = sum(1 for r in deduped_results if r.status == MatchStatus.CONFIRMED_MATCH)
    potential = sum(1 for r in deduped_results if r.status == MatchStatus.POTENTIAL_MATCH)
    clear = sum(1 for r in deduped_results if r.status == MatchStatus.CLEAR)

    # Unike entiteter screenet
    unique_entities = len({str(r.entity_id) for r in deduped_results})

    return ScreeningResultsResponse(
        invoice_id=invoice_id,
        compliance_score=invoice.compliance_score.value if invoice.compliance_score else None,
        results=result_reads,
        screened_at=screened_at,
        total_entities=unique_entities,
        confirmed_matches=confirmed,
        potential_matches=potential,
        clear=clear,
    )


@invoice_router.get(
    "/{invoice_id}/screening/candidates",
    response_model=ScreeningCandidatesResponse,
    summary="Vis kandidater brukt i screening (debug)",
)
async def get_screening_candidates(
    invoice_id: uuid.UUID,
    session: SessionDep,
) -> ScreeningCandidatesResponse:
    """Returner kandidatlisten brukt av screeningmotoren for invoicen."""
    invoice = await get_invoice(session, invoice_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} finnes ikke",
        )

    latest_run = await screening_service.get_latest_screening_run(session, invoice_id)
    mode = "preview"
    rows: list[dict[str, Any]]
    run_id = None
    run_status = None
    run_started_at = None
    run_finished_at = None

    if latest_run:
        snapshot_rows = await screening_service.get_screening_candidates_from_run(
            session,
            latest_run.id,
        )
        rows = [
            {
                "key": str(row.id),
                "entity_id": row.entity_id,
                "entity_name": row.entity_name,
                "entity_role": row.entity_role,
                "candidate_name": row.candidate_name,
                "entity_type": row.entity_type,
                "country": row.country,
                "source": row.source,
                "source_email": row.source_email,
                "primary": row.is_primary,
            }
            for row in snapshot_rows
        ]
        mode = "snapshot"
        run_id = latest_run.id
        run_status = latest_run.status
        run_started_at = latest_run.started_at
        run_finished_at = latest_run.finished_at
    else:
        rows = await screening_service.get_screening_candidates_preview(session, invoice_id)

    return ScreeningCandidatesResponse(
        invoice_id=invoice_id,
        run_id=run_id,
        run_status=run_status,
        run_started_at=run_started_at,
        run_finished_at=run_finished_at,
        mode=mode,
        total=len(rows),
        items=[ScreeningCandidateDebugRead.model_validate(row) for row in rows],
    )


# ── Yente-administrasjon ──────────────────────────────────────────────────────


@admin_router.get(
    "/status",
    response_model=SanctionsStatusResponse,
    summary="Yente-status og datasett-oversikt",
)
async def get_sanctions_status() -> SanctionsStatusResponse:
    """Hent status for yente-tjenesten og alle konfigurerte sanksjonslister."""
    settings = get_settings()
    yente = get_yente_client()
    healthy = await yente.is_healthy()
    es_available, es_error = await _elasticsearch_status()
    local_sources = []
    external_sources = []
    latest_refresh = None

    from app.core.database import get_session_factory

    async with get_session_factory()() as local_session:
        rows = await list_local_sanctions_statuses(local_session)
        latest_refresh = await get_latest_refresh_run(local_session)
        external_health_rows = await list_external_source_health(local_session)
        local_sources = [
            LocalSanctionsSourceStatus(
                source=row.source,
                last_updated=row.last_updated,
                entry_count=row.entry_count,
                update_status=row.update_status,
                error_message=row.error_message,
            )
            for row in rows
        ]
        external_sources = [
            ExternalSourceHealthStatus(
                source=str(row.get("source")),
                enabled=bool(row.get("enabled")),
                status=str(row.get("status")),
                entry_count=(int(row.get("entry_count")) if isinstance(row.get("entry_count"), int | float) else None),
                last_updated=(row.get("last_updated") if isinstance(row.get("last_updated"), datetime) else None),
                error_message=(str(row.get("error_message")) if row.get("error_message") else None),
                stale=bool(row.get("stale")),
            )
            for row in external_health_rows
            if isinstance(row, dict)
        ]

    if not healthy:
        return SanctionsStatusResponse(
            yente_available=False,
            elasticsearch_available=es_available,
            elasticsearch_error=es_error,
            yente_version=None,
            datasets=[],
            local_sources=local_sources,
            external_sources=external_sources,
            refresh_schedule_time=f"{settings.sanctions_refresh_hour:02d}:{settings.sanctions_refresh_minute:02d}",
            refresh_schedule_timezone=settings.celery_timezone,
            external_refresh_schedule_time=(
                f"{settings.external_source_refresh_hour:02d}:{settings.external_source_refresh_minute:02d}"
            ),
            last_refresh_run=(
                SanctionsRefreshRunStatus(
                    trigger=latest_refresh.trigger,
                    status=latest_refresh.status,
                    message=latest_refresh.message,
                    started_at=latest_refresh.started_at,
                    finished_at=latest_refresh.finished_at,
                )
                if latest_refresh
                else None
            ),
        )

    version = await yente.get_version()
    raw_datasets = await yente.list_datasets()

    datasets = [
        YenteDatasetStatus(
            name=ds.name,
            title=ds.title,
            entity_count=ds.entity_count,
            last_updated=ds.last_updated,
            status=ds.status,
        )
        for ds in raw_datasets
    ]

    return SanctionsStatusResponse(
        yente_available=True,
        elasticsearch_available=es_available,
        elasticsearch_error=es_error,
        yente_version=version,
        datasets=datasets,
        local_sources=local_sources,
        external_sources=external_sources,
        refresh_schedule_time=f"{settings.sanctions_refresh_hour:02d}:{settings.sanctions_refresh_minute:02d}",
        refresh_schedule_timezone=settings.celery_timezone,
        external_refresh_schedule_time=(
            f"{settings.external_source_refresh_hour:02d}:{settings.external_source_refresh_minute:02d}"
        ),
        last_refresh_run=(
            SanctionsRefreshRunStatus(
                trigger=latest_refresh.trigger,
                status=latest_refresh.status,
                message=latest_refresh.message,
                started_at=latest_refresh.started_at,
                finished_at=latest_refresh.finished_at,
            )
            if latest_refresh
            else None
        ),
    )


@admin_router.post(
    "/refresh",
    response_model=SanctionsRefreshResponse,
    summary="Oppdater sanksjonslister",
    response_description="Datasett-nedlasting og reindeksering er trigget i yente.",
)
async def refresh_sanctions(
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> SanctionsRefreshResponse:
    """Trigger manuell oppdatering av yente-datasett.

    Yente laster ned og reindekserer alle datasett konfigurert i manifest.yml.
    Dette kan ta 5-15 minutter avhengig av nedlastingshastighet.
    """
    yente = get_yente_client()
    healthy = await yente.is_healthy()

    if not healthy:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Yente-tjenesten er ikke tilgjengelig. Sjekk at Docker-kontaineren kjorer.",
        )

    settings = get_settings()
    if settings.use_celery_background:
        try:
            from app.tasks.update_sanctions import run as update_sanctions_task

            update_sanctions_task.delay()
        except Exception as exc:
            logger.warning("yente_refresh_celery_enqueue_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Kunne ikke triggere reindeksering via Celery: {exc}",
            ) from exc
    else:
        try:
            refresh_result = await run_sanctions_refresh_cycle_with_trigger(trigger="manual")
            if not refresh_result.started:
                return SanctionsRefreshResponse(
                    message=refresh_result.message,
                    datasets_triggered=[],
                )
        except Exception as exc:
            logger.warning("yente_refresh_failed", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Kunne ikke triggere reindeksering: {exc}",
            ) from exc

    raw_datasets = await yente.list_datasets()
    names = [ds.name for ds in raw_datasets]

    return SanctionsRefreshResponse(
        message="Reindeksering trigget. Yente laster ned og indekserer datasettene.",
        datasets_triggered=names,
    )


@admin_router.post(
    "/external-sources/refresh",
    response_model=SanctionsRefreshResponse,
    summary="Oppdater eksterne screening-kilder",
)
async def refresh_external_sources(
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> SanctionsRefreshResponse:
    """Trigger manuell ingest av UK/WorldBank for utvidet screening."""
    result = await run_external_watchlist_ingest_cycle()
    if not bool(result.get("started")):
        return SanctionsRefreshResponse(
            message=str(result.get("message") or "Ekstern refresh hoppet over."),
            datasets_triggered=[],
        )
    sources = [str(row.get("source")) for row in (result.get("sources") or []) if isinstance(row, dict)]
    return SanctionsRefreshResponse(
        message=str(result.get("message") or "Eksterne kilder oppdatert."),
        datasets_triggered=sources,
    )


@admin_router.get(
    "/pipeline/metrics",
    response_model=PipelineMetricsResponse,
    summary="Pipeline SLA-metrikker",
)
async def get_pipeline_metrics_endpoint(
    session: SessionDep,
    lookback_hours: int = Query(24, ge=1, le=24 * 14),
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> PipelineMetricsResponse:
    """Aggreger driftstall for parsing/ekstraksjon/screening."""
    return await get_pipeline_metrics(
        session,
        lookback_hours=lookback_hours,
    )


@admin_router.get(
    "/pipeline/recovery",
    response_model=PipelineRecoveryResponse,
    summary="Finn invoices som trenger recovery",
)
async def get_pipeline_recovery_endpoint(
    session: SessionDep,
    stale_minutes: int = Query(10, ge=1, le=24 * 60),
    limit: int = Query(100, ge=1, le=500),
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> PipelineRecoveryResponse:
    """Returner stale/failed invoices for operativ oppfølging."""
    return await list_pipeline_recovery_candidates(
        session,
        stale_minutes=stale_minutes,
        limit=limit,
    )


def _default_recovery_target(invoice: Invoice) -> str:
    if invoice.status in {InvoiceStatus.PARSING, InvoiceStatus.PARSING_FAILED}:
        return "parse"
    if invoice.status in {
        InvoiceStatus.PARSED,
        InvoiceStatus.EXTRACTING,
        InvoiceStatus.EXTRACTION_FAILED,
    }:
        return "extract"
    if invoice.status in {
        InvoiceStatus.EXTRACTED,
        InvoiceStatus.SCREENING,
        InvoiceStatus.SCREENING_FAILED,
        InvoiceStatus.SCREENED,
    }:
        return "screen"
    return "parse"


@admin_router.post(
    "/pipeline/recovery/{invoice_id}/retry",
    response_model=PipelineRecoveryActionResponse,
    summary="Retry invoice i valgt pipeline-steg",
)
async def retry_pipeline_invoice(
    invoice_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    target: str = Query(
        "auto",
        pattern="^(auto|parse|extract|screen)$",
        description="Steg å retry'e. auto velger fra nåværende status.",
    ),
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> PipelineRecoveryActionResponse:
    invoice = await get_invoice_for_recovery(session, invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} finnes ikke.",
        )

    chosen = _default_recovery_target(invoice) if target == "auto" else target
    settings = get_settings()

    if chosen == "parse":
        prev_status = invoice.status.value
        invoice.status = InvoiceStatus.UPLOADED
        invoice.raw_text = None
        invoice.parsing_error = None
        invoice.extraction_error = None
        invoice.compliance_score = None
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="parsing",
            action="queued",
            status_from=prev_status,
            status_to=InvoiceStatus.UPLOADED.value,
            message="Recovery retry queued for parse.",
        )
        await session.commit()

        if settings.use_celery_background:
            try:
                from app.tasks.process_invoice import run as process_invoice_task

                process_invoice_task.delay(str(invoice.id), str(invoice.pdf_path))
            except Exception as exc:
                logger.exception(
                    "pipeline_recovery_parse_enqueue_failed",
                    invoice_id=str(invoice.id),
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Klarte ikke å queue parsing: {exc}",
                ) from exc
        else:
            from pathlib import Path

            from app.services.invoice_service import parse_invoice_in_background

            background_tasks.add_task(parse_invoice_in_background, invoice.id, Path(invoice.pdf_path))

        return PipelineRecoveryActionResponse(
            invoice_id=invoice.id,
            target="parse",
            message="Re-parse queued.",
        )

    if chosen == "extract":
        if not invoice.raw_text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invoice mangler raw_text og må parses først.",
            )
        prev_status = invoice.status.value
        invoice.status = InvoiceStatus.PARSED
        invoice.extraction_error = None
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="extracting",
            action="queued",
            status_from=prev_status,
            status_to=InvoiceStatus.PARSED.value,
            message="Recovery retry queued for extract.",
        )
        await session.commit()

        if settings.use_celery_background:
            try:
                from app.tasks.extract_invoice import run as extract_invoice_task

                extract_invoice_task.delay(str(invoice.id))
            except Exception as exc:
                logger.exception(
                    "pipeline_recovery_extract_enqueue_failed",
                    invoice_id=str(invoice.id),
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Klarte ikke å queue ekstraksjon: {exc}",
                ) from exc
        else:
            background_tasks.add_task(_run_extraction_background, invoice.id)

        return PipelineRecoveryActionResponse(
            invoice_id=invoice.id,
            target="extract",
            message="Re-extract queued.",
        )

    if chosen == "screen":
        if invoice.status not in {
            InvoiceStatus.EXTRACTED,
            InvoiceStatus.SCREENED,
            InvoiceStatus.SCREENING_FAILED,
            InvoiceStatus.SCREENING,
        }:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invoice må være ekstrahert før screening kan restartes.",
            )
        prev_status = invoice.status.value
        invoice.status = InvoiceStatus.SCREENING
        await append_pipeline_event(
            session,
            invoice_id=invoice.id,
            stage="screening",
            action="queued",
            status_from=prev_status,
            status_to=InvoiceStatus.SCREENING.value,
            message="Recovery retry queued for screen.",
        )
        await session.commit()

        if settings.use_celery_background:
            try:
                from app.tasks.screen_entities import run as screen_entities_task

                screen_entities_task.delay(str(invoice.id))
            except Exception as exc:
                logger.exception(
                    "pipeline_recovery_screen_enqueue_failed",
                    invoice_id=str(invoice.id),
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Klarte ikke å queue screening: {exc}",
                ) from exc
        else:
            background_tasks.add_task(_run_screening_background, invoice.id)

        return PipelineRecoveryActionResponse(
            invoice_id=invoice.id,
            target="screen",
            message="Re-screen queued.",
        )

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=f"Ugyldig target: {chosen}",
    )


@admin_router.get(
    "/entities",
    response_model=SanctionedEntityListResponse,
    summary="List og søk i sanksjonerte entiteter",
)
async def list_sanctioned_entities(
    q: str = Query("", description="Fritekst for fuzzy søk"),
    entity_type: str = Query(
        "all",
        pattern="^(all|company|person)$",
        description="all=person+selskap, company=kun selskaper, person=kun personer",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    fuzzy: bool = Query(True),
    simple: bool = Query(True),
) -> SanctionedEntityListResponse:
    """Hent sanksjonerte entiteter fra yente med paginering og fuzzy søk."""
    yente = get_yente_client()
    if not await yente.is_healthy():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Yente-tjenesten er ikke tilgjengelig.",
        )

    if entity_type == "person":
        payload = await yente.search_entities(
            query=q,
            schema="Person",
            topics=["sanction"],
            limit=limit,
            offset=offset,
            fuzzy=fuzzy,
            simple=simple,
        )
        items = [
            SanctionedEntityRead(
                id=e.id,
                caption=e.caption,
                schema=e.schema,
                datasets=e.datasets,
                countries=e.countries,
                topics=e.topics,
                first_seen=e.first_seen,
                last_seen=e.last_seen,
                last_change=e.last_change,
            )
            for e in payload.items
        ]
        return SanctionedEntityListResponse(
            items=items,
            total=payload.total,
            total_relation=payload.total_relation,
            limit=limit,
            offset=offset,
            query=q,
            entity_type=entity_type,
        )

    if entity_type == "company":
        payload = await yente.search_entities(
            query=q,
            schema="LegalEntity",
            topics=["sanction"],
            limit=limit,
            offset=offset,
            fuzzy=fuzzy,
            simple=simple,
        )
        items = [
            SanctionedEntityRead(
                id=e.id,
                caption=e.caption,
                schema=e.schema,
                datasets=e.datasets,
                countries=e.countries,
                topics=e.topics,
                first_seen=e.first_seen,
                last_seen=e.last_seen,
                last_change=e.last_change,
            )
            for e in payload.items
        ]
        return SanctionedEntityListResponse(
            items=items,
            total=payload.total,
            total_relation=payload.total_relation,
            limit=limit,
            offset=offset,
            query=q,
            entity_type=entity_type,
        )

    # all: filtrer Thing til person/selskap-skjemaer.
    collected: list[SanctionedEntityRead] = []
    filtered_seen = 0
    yente_offset = 0
    page_size = min(200, max(100, limit * 4))
    total = 0
    total_relation = "eq"

    while len(collected) < limit:
        payload = await yente.search_entities(
            query=q,
            schema="Thing",
            topics=["sanction"],
            limit=page_size,
            offset=yente_offset,
            fuzzy=fuzzy,
            simple=simple,
        )
        total = payload.total
        total_relation = payload.total_relation

        if not payload.items:
            break

        filtered = [e for e in payload.items if e.schema and e.schema.lower() in _COMPANY_OR_PERSON_SCHEMAS]
        for entity in filtered:
            if filtered_seen < offset:
                filtered_seen += 1
                continue
            if len(collected) >= limit:
                break
            collected.append(
                SanctionedEntityRead(
                    id=entity.id,
                    caption=entity.caption,
                    schema=entity.schema,
                    datasets=entity.datasets,
                    countries=entity.countries,
                    topics=entity.topics,
                    first_seen=entity.first_seen,
                    last_seen=entity.last_seen,
                    last_change=entity.last_change,
                )
            )

        yente_offset += len(payload.items)
        if len(payload.items) < page_size or yente_offset >= 9500:
            break

    return SanctionedEntityListResponse(
        items=collected,
        total=total,
        total_relation=total_relation,
        limit=limit,
        offset=offset,
        query=q,
        entity_type=entity_type,
    )
