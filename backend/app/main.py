"""
FastAPI-applikasjonen.

Denne modulen samler oppstartslogikk: konfigurasjon, logging, CORS,
feilhåndterere og router-mounting. Selve forretningslogikken ligger i
underliggende moduler.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

_startup_tasks: set[object] = set()


def _track_startup_task(task: object) -> None:
    """Behold referanse til startup-task for å unngå garbage collection."""
    _startup_tasks.add(task)
    if hasattr(task, "add_done_callback"):
        task.add_done_callback(_startup_tasks.discard)


def _make_minimal_pdf() -> bytes:
    """Bygg en minimal men syntaktisk gyldig PDF for pre-warming av Docling."""
    objects = [
        b"1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n",
        b"2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n",
        b"3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>\nendobj\n",
    ]
    header = b"%PDF-1.4\n"
    pos = len(header)
    offsets: list[int] = []
    body = b""
    for obj in objects:
        offsets.append(pos)
        body += obj
        pos += len(obj)
    xref_pos = pos
    xref = b"xref\n0 4\n0000000000 65535 f\r\n"
    for off in offsets:
        xref += f"{off:010d} 00000 n\r\n".encode()
    trailer = b"trailer\n<</Size 4/Root 1 0 R>>\nstartxref\n"
    trailer += str(xref_pos).encode() + b"\n%%EOF\n"
    return header + body + xref + trailer


def _warm_docling(logger: object) -> None:  # type: ignore[type-arg]
    """Pre-warm Docling ML-modeller i en thread-pool under oppstart.

    Docling laster layout-deteksjon, tabellstruktur og OCR-modeller LAZY
    ved første convert()-kall. Uten pre-warming henger første brukerforespørsel
    i 2–3 min mens modellene (hundrevis av MB) lastes fra disk til RAM/GPU.
    """
    try:
        from app.core.gpu import get_gpu_info

        gpu = get_gpu_info()
        logger.info(  # type: ignore[union-attr]
            "gpu_status",
            available=gpu.available,
            device=gpu.device,
            name=gpu.name,
            vram_mb=gpu.vram_mb,
        )

        from app.parsers.docling_parser import (
            _get_image_converter,
            _get_standard_converter,
            _get_xlsx_converter,
        )

        std_conv = _get_standard_converter()
        _get_xlsx_converter()
        _get_image_converter()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as _f:
            _f.write(_make_minimal_pdf())
            _dummy_path = Path(_f.name)
        try:
            std_conv.convert(str(_dummy_path))
            logger.info("docling_models_warmed")  # type: ignore[union-attr]
        finally:
            _dummy_path.unlink(missing_ok=True)

        logger.info("docling_prewarmed")  # type: ignore[union-attr]

        try:
            import easyocr

            gpu_flag = gpu.available and gpu.device == "cuda"
            easyocr.Reader(["en"], gpu=gpu_flag, verbose=False)
            logger.info("easyocr_models_cached", gpu=gpu_flag)  # type: ignore[union-attr]
        except ImportError:
            pass  # easyocr ikke installert — RapidOCR brukes som fallback
        except Exception as exc:
            logger.warning("easyocr_prewarm_failed", error=str(exc))  # type: ignore[union-attr]
    except Exception as exc:
        logger.warning("docling_prewarm_failed", error=str(exc))  # type: ignore[union-attr]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialisering ved oppstart og opprydding ved nedstenging."""
    configure_logging()
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    logger = get_logger(__name__)
    logger.info(
        "application_started",
        env=settings.app_env,
        upload_dir=str(settings.upload_dir),
    )

    # V1: Advar ved oppstart om usikker standardnøkkel.
    if settings.app_secret_key.get_secret_value() == "change-me":
        logger.warning(
            "insecure_default_secret_key",
            message=(
                "APP_SECRET_KEY er ikke satt — standardverdien 'change-me' brukes. "
                "Sett APP_SECRET_KEY til en tilfeldig, lang streng i .secrets "
                "før systemet eksponeres eksternt."
            ),
        )

    # Pre-warm Docling i bakgrunnen (se _warm_docling for detaljer).
    asyncio.get_running_loop().run_in_executor(None, _warm_docling, logger)

    # Seed embargo-data, bootstrap sync-status ved behov, og last cache fra DB.
    try:
        from app.core.database import get_session_factory
        from app.services.export_control_service import seed_reference_categories
        from app.sanctions.embargo import load_cache_from_db, seed_db_from_static

        async with get_session_factory()() as _s:
            seeded = await seed_db_from_static(_s)
            if seeded:
                logger.info("embargo_seed_complete", count=seeded)

            ec_seeded = await seed_reference_categories(_s)
            if ec_seeded:
                logger.info("export_control_seed_complete", count=ec_seeded)

            await _s.commit()

            loaded = await load_cache_from_db(_s)
            if loaded:
                logger.info("embargo_cache_loaded", count=loaded)
    except Exception:
        logger.exception("embargo_startup_failed")

    # Startup-recovery: finn invoices som satt fast under forrige kjøring.
    # Kjøres som en async task slik at oppstart ikke blokkeres.
    _track_startup_task(asyncio.create_task(_recover_stuck_invoices(logger, settings)))

    yield

    logger.info("application_stopped")


async def _recover_stuck_invoices(logger: object, settings: object) -> None:  # type: ignore[type-arg]
    """Gjenoppta invoices som satt fast ved forrige restart.

    'parsing'    → serveren ble restartet mens Docling kjørte → re-parsér fra disk.
    'parsed'     → serveren ble restartet etter parsing men før LLM-ekstraksjon → start extraction.
    'extracting' → serveren ble restartet midt i LLM-ekstraksjon → re-start extraction.
    'screening'  → worker/API døde midt i screening → markeres som screening_failed.
    """
    import asyncio as _asyncio
    from pathlib import Path as _Path

    from sqlalchemy import select as _select

    from app.core.database import get_session_factory
    from app.models.invoice import Invoice as _Invoice
    from app.models.invoice import InvoiceStatus as _InvoiceStatus
    from app.services.invoice_service import parse_invoice_in_background

    # Vent litt så DB og pre-warming rekker å starte
    await _asyncio.sleep(2)

    async with get_session_factory()() as session:
        result = await session.execute(
            _select(_Invoice).where(
                _Invoice.status.in_(
                    [
                        _InvoiceStatus.PARSING,
                        _InvoiceStatus.PARSED,
                        _InvoiceStatus.EXTRACTING,
                        _InvoiceStatus.SCREENING,
                    ]
                )
            )
        )
        stuck = result.scalars().all()

    if not stuck:
        return

    logger.info("startup_recovery_found", count=len(stuck))  # type: ignore[attr-defined]

    for invoice in stuck:
        iid = invoice.id
        ifile = _Path(invoice.pdf_path)
        istatus = invoice.status

        if istatus == _InvoiceStatus.PARSING:
            # Re-parsér fra lagret fil — setter status tilbake til UPLOADED først
            async with get_session_factory()() as session:
                inv = await session.get(_Invoice, iid)
                if inv:
                    inv.status = _InvoiceStatus.UPLOADED
                    inv.parsing_error = None
                    await session.commit()
            _track_startup_task(_asyncio.create_task(parse_invoice_in_background(iid, ifile)))
            logger.info("startup_recovery_requeue_parse", invoice_id=str(iid))  # type: ignore[attr-defined]

        elif istatus in {_InvoiceStatus.PARSED, _InvoiceStatus.EXTRACTING} and (
            settings.auto_extract_after_parse or istatus == _InvoiceStatus.EXTRACTING
        ):
            # Trigger ekstraksjon direkte — parsing er allerede ferdig
            async def _do_extract(invoice_id: object = iid) -> None:  # type: ignore[type-arg]
                from app.services.extraction_service import run_extraction

                try:
                    async with get_session_factory()() as ext_session:
                        await run_extraction(ext_session, invoice_id)  # type: ignore[arg-type]
                        logger.info(
                            "startup_recovery_extraction_done",
                            invoice_id=str(invoice_id),
                        )  # type: ignore[attr-defined]
                except Exception:
                    logger.exception(
                        "startup_recovery_extraction_failed",
                        invoice_id=str(invoice_id),
                    )  # type: ignore[attr-defined]

            _track_startup_task(_asyncio.create_task(_do_extract()))
            logger.info(
                "startup_recovery_requeue_extract",
                invoice_id=str(iid),
                from_status=istatus.value,
            )  # type: ignore[attr-defined]

        elif istatus == _InvoiceStatus.SCREENING:
            async with get_session_factory()() as session:
                from datetime import UTC as _UTC
                from datetime import datetime as _datetime

                from sqlalchemy import select as _select2

                from app.models.screening_run import ScreeningRun as _ScreeningRun

                inv = await session.get(_Invoice, iid)
                if inv:
                    inv.status = _InvoiceStatus.SCREENING_FAILED
                    inv.compliance_score = None

                    run_res = await session.execute(
                        _select2(_ScreeningRun)
                        .where(_ScreeningRun.invoice_id == iid)
                        .order_by(_ScreeningRun.started_at.desc())
                        .limit(1)
                    )
                    run = run_res.scalars().first()
                    if run is not None and run.status == "running":
                        run.status = "failed"
                        run.error_message = "Recovered on startup: screening was interrupted."
                        run.finished_at = _datetime.now(_UTC)

                    await session.commit()
            logger.warning(
                "startup_recovery_mark_screening_failed",
                invoice_id=str(iid),
            )  # type: ignore[attr-defined]


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AI-drevet compliance-tjeneste for norske eksportbedrifter.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.app_api_v1_prefix)

    return app


app = create_app()
