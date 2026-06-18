"""
Dokumentparsing via Docling — støtter PDF og XLSX.

Alle Docling-imports er lazy (inne i funksjoner) for å holde oppstartstiden
lav. Docling drar med seg store ML-avhengigheter som ikke skal lastes før
en faktisk parsing starter.

Konvertere caches som module-level singletons etter første bruk — Docling
er dyr å instansiere (modellvekter lastes), men rask å kalle gjentatte ganger.

Pipeline-modi (gjelder kun PDF):
  standard    — Doclings innebygde pipeline. TableFormer for tabeller,
                EasyOCR for skannet materiale. Ingen API-nøkkel.
                Modeller lastes ned ved første kjøring (~1-2 GB).
  multimodal  — OpenAI vision-API for sideforståelse. Krever OPENAI_API_KEY
                i .secrets. Sender sidebilder til OpenAI.
                GDPR-note: databehandleravtale med OpenAI må være på plass.

XLSX:
  Docling leser Excel-filer nativt. Arkene konverteres til Markdown-tabeller
  slik at LLM-ekstraksjon (Sprint 2) kan behandle dem likt med PDF-tekst.
  Pipeline-parameteret ignoreres for XLSX.

GPU:
  Aktiveres automatisk ved å sette OCR_USE_GPU i .env.
  Bruker Doclings AcceleratorOptions (CUDA/MPS/CPU) og EasyOcrOptions.use_gpu.
  AcceleratorDevice.AUTO er Doclings standardvalg for interne modeller
  (layout, TableFormer), men EasyOCR har bruk_gpu=False som standard og
  må eksplisitt slås på.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from app.core.config import get_settings
from app.core.errors import ParsingError
from app.core.logging import get_logger
from app.parsers.models import ParsedDocument, ParserMethod, SourceFileType

if TYPE_CHECKING:
    # Brukes kun av type-checker — lastes aldri ved kjøretid
    from docling.document_converter import DocumentConverter

logger = get_logger(__name__)

# Lazy singletons. Opprettet første gang konverteren brukes, deretter gjenbrukt.
_standard_converter: DocumentConverter | None = None
_multimodal_converter: DocumentConverter | None = None
_xlsx_converter: DocumentConverter | None = None  # XLSX — ingen OCR
_image_converter: DocumentConverter | None = None  # Bilde-fallback EasyOCR


def _get_standard_converter() -> DocumentConverter:
    """Returner (og opprett ved behov) standard PDF-konverter med GPU-støtte.

    Konfigurerer:
      - AcceleratorOptions  → GPU for Doclings interne modeller (layout, TableFormer)
      - EasyOcrOptions      → GPU for OCR (bruk_gpu er False som standard i EasyOCR)

    GPU-valget styres av settings.ocr_use_gpu:
      None  → auto-detekter via get_gpu_info()
      True  → tving GPU
      False → tving CPU
    """
    global _standard_converter
    if _standard_converter is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import AcceleratorOptions, PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

        from app.core.gpu import get_gpu_info

        settings = get_settings()
        gpu = get_gpu_info()
        use_gpu = _resolve_gpu_flag(settings.ocr_use_gpu, gpu.available)
        accel_device = _gpu_to_accelerator_device(gpu.device, use_gpu)

        pipeline_options = PdfPipelineOptions(
            do_ocr=True,
            do_table_structure=True,
            generate_page_images=False,
            accelerator_options=AcceleratorOptions(device=accel_device),
            ocr_options=_make_ocr_options(),
        )
        _standard_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=StandardPdfPipeline,
                    pipeline_options=pipeline_options,
                )
            }
        )
        logger.info(
            "docling_standard_converter_initialized",
            accel_device=accel_device.value,
            gpu_name=gpu.name,
        )
    return _standard_converter


def _get_multimodal_converter() -> DocumentConverter:
    """Returner (og opprett ved behov) multimodal Docling-konverter via OpenAI.

    Faller tilbake til standard-converter hvis OPENAI_API_KEY mangler.
    """
    global _multimodal_converter
    if _multimodal_converter is None:
        settings = get_settings()
        api_key = settings.openai_api_key_value

        if not api_key:
            logger.warning(
                "docling_multimodal_no_api_key_falling_back_to_standard",
                hint="Legg OPENAI_API_KEY i .secrets for å aktivere multimodal parsing.",
            )
            return _get_standard_converter()

        # Lazy import — lastes kun hvis multimodal faktisk er konfigurert
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import VlmPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.models.vlms.openai_options import OpenAiVlmOptions  # type: ignore[import]
        from docling.pipeline.vlm_pipeline import VlmPipeline

        vlm_options = OpenAiVlmOptions(
            api_key=api_key,
            model=settings.docling_vlm_model,
        )
        _multimodal_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=VlmPipeline,
                    pipeline_options=VlmPipelineOptions(vlm_options=vlm_options),
                )
            }
        )
        logger.info(
            "docling_multimodal_converter_initialized",
            model=settings.docling_vlm_model,
        )
    return _multimodal_converter


def _get_xlsx_converter() -> DocumentConverter:
    """Returner (og opprett ved behov) en enkel Docling-konverter for XLSX.

    XLSX leses nativt av Docling uten OCR — ingen GPU-konfig nødvendig.
    """
    global _xlsx_converter
    if _xlsx_converter is None:
        from docling.document_converter import DocumentConverter

        _xlsx_converter = DocumentConverter()
        logger.info("docling_xlsx_converter_initialized")
    return _xlsx_converter


def _get_image_converter() -> DocumentConverter:
    """Returner (og opprett ved behov) Docling-konverter for bildefiler (EasyOCR-fallback).

    Bruker ImageFormatOption med ThreadedPdfPipelineOptions for å konfigurere
    EasyOCR og GPU-akselerasjon riktig.  Dette er fallback-stien som kun brukes
    hvis OPENAI_API_KEY mangler eller Vision-kallet feiler.
    """
    global _image_converter
    if _image_converter is None:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            AcceleratorOptions,
            ThreadedPdfPipelineOptions,
        )
        from docling.document_converter import DocumentConverter, ImageFormatOption

        from app.core.gpu import get_gpu_info

        settings = get_settings()
        gpu = get_gpu_info()
        use_gpu = _resolve_gpu_flag(settings.ocr_use_gpu, gpu.available)
        accel_device = _gpu_to_accelerator_device(gpu.device, use_gpu)

        # ImageFormatOption bruker ThreadedPdfPipelineOptions (ikke PdfPipelineOptions)
        # for sin interne pipeline. Vi konfigurerer OCR og akselerasjon eksplisitt.
        image_pipeline_options = ThreadedPdfPipelineOptions(
            do_ocr=True,
            do_table_structure=True,
            generate_page_images=False,
            accelerator_options=AcceleratorOptions(device=accel_device),
            ocr_options=_make_ocr_options(),
        )
        _image_converter = DocumentConverter(
            format_options={
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_options=image_pipeline_options,
                )
            }
        )
        logger.info(
            "docling_image_converter_initialized",
            accel_device=accel_device.value,
        )
    return _image_converter


# ── Hjelpefunksjoner ───────────────────────────────────────────────────────────


def _resolve_gpu_flag(setting: bool | None, gpu_available: bool) -> bool:
    """Oversett settings.ocr_use_gpu til en konkret bool.

    Args:
        setting:       Verdi fra Settings.ocr_use_gpu (None=auto, True=tving GPU, False=tving CPU).
        gpu_available: Resultat fra get_gpu_info().available.
    """
    if setting is None:
        return gpu_available  # auto-deteksjon
    return setting


def _gpu_to_accelerator_device(device_str: str, use_gpu: bool):  # type: ignore[return]
    """Konverter GpuInfo.device-streng til Doclings AcceleratorDevice-enum.

    Returtype er AcceleratorDevice (lazy-importert — ikke mulig å annotere uten
    å laste Docling ved modulimport).
    """
    from docling.datamodel.pipeline_options import AcceleratorDevice

    if not use_gpu:
        return AcceleratorDevice.CPU
    mapping = {"cuda": AcceleratorDevice.CUDA, "mps": AcceleratorDevice.MPS}
    return mapping.get(device_str, AcceleratorDevice.AUTO)


def _make_ocr_options():  # type: ignore[return]
    """Lag riktige OCR-alternativer basert på hva som er installert.

    Prioritering:
      1. EasyOcrOptions — hvis easyocr-pakken er installert.
         GPU styres av AcceleratorOptions.device (ikke use_gpu — deprecated i Docling 2.x).
      2. OcrAutoOptions — Docling velger selv (f.eks. RapidOCR).

    Dette forhindrer ImportError når easyocr ikke er installert, og gir
    GPU-akselerasjon via AcceleratorOptions når det er tilgjengelig.
    """
    try:
        import easyocr as _  # noqa: F401 — sjekk at pakken finnes
        from docling.datamodel.pipeline_options import EasyOcrOptions

        # Ikke sett use_gpu — deprecated i Docling 2.x.
        # GPU styres i stedet av AcceleratorOptions.device i PdfPipelineOptions.
        return EasyOcrOptions(force_full_page_ocr=False)
    except ImportError:
        from docling.datamodel.pipeline_options import OcrAutoOptions

        logger.debug(
            "easyocr_not_installed_using_auto_ocr",
            hint="Installer 'easyocr' for GPU-akselerert OCR.",
        )
        return OcrAutoOptions()


# ── Offentlig API ──────────────────────────────────────────────────────────────


def extract_text(
    file_path: Path,
    pipeline: Literal["standard", "multimodal"] | None = None,
) -> ParsedDocument:
    """Parse et invoice-dokument (PDF eller XLSX) med Docling.

    Docling-biblioteket lastes lazy ved første kall — oppstartstiden til
    API-et påvirkes ikke av at denne modulen importeres.

    For XLSX ignoreres pipeline-parameteret — Docling leser Excel nativt
    uten OCR eller VLM, og arkene eksporteres som Markdown-tabeller.

    Args:
        file_path: Sti til filen på disk (PDF eller XLSX).
        pipeline:  Overstyring av PDF-pipeline. None → bruk Settings.docling_pipeline.

    Returns:
        ParsedDocument med Markdown-tekst og metadata.

    Raises:
        ParsingError: Hvis filen mangler eller Docling feiler.
    """
    if not file_path.exists():
        raise ParsingError(
            f"Fil finnes ikke: {file_path}",
            details={"path": str(file_path)},
        )

    file_type = SourceFileType.from_filename(file_path.name)
    log = logger.bind(file_path=str(file_path), file_type=file_type.value)

    if file_type == SourceFileType.XLSX:
        return _extract_xlsx(file_path, log)

    if file_type == SourceFileType.IMAGE:
        return _extract_image(file_path, log)

    return _extract_pdf(file_path, pipeline, log)


def _extract_pdf(
    file_path: Path,
    pipeline: Literal["standard", "multimodal"] | None,
    log: object,
) -> ParsedDocument:
    settings = get_settings()
    active_pipeline = pipeline or settings.docling_pipeline

    converter = _get_multimodal_converter() if active_pipeline == "multimodal" else _get_standard_converter()

    try:
        log.info("docling_pdf_conversion_started", pipeline=active_pipeline)  # type: ignore[attr-defined]
        result = converter.convert(str(file_path))
    except Exception as exc:
        raise ParsingError(
            "Docling klarte ikke å konvertere PDF-filen.",
            details={"path": str(file_path), "error": str(exc)},
        ) from exc

    markdown_text = result.document.export_to_markdown()
    page_count = len(result.document.pages) if hasattr(result.document, "pages") else 1
    method = ParserMethod.OCR if active_pipeline == "multimodal" else ParserMethod.DIGITAL

    log.info("docling_conversion_done", page_count=page_count, text_length=len(markdown_text))  # type: ignore[attr-defined]
    return ParsedDocument(
        text=markdown_text,
        method=method,
        page_count=page_count,
        file_type=SourceFileType.PDF,
        pages=[],
        ocr_pages=0,
    )


def _extract_xlsx(file_path: Path, log: object) -> ParsedDocument:
    """Les en Excel-fil med Docling og eksporter arkene som Markdown-tabeller.

    Docling konverterer hvert ark til en strukturert Markdown-tabell. Dette
    gjør at LLM-ekstraksjon (Sprint 2) kan behandle Excel-invoices på samme
    måte som PDF-tekst — ingen separat kodesti nødvendig.
    """
    try:
        log.info("docling_xlsx_conversion_started")  # type: ignore[attr-defined]
        result = _get_xlsx_converter().convert(str(file_path))
    except Exception as exc:
        raise ParsingError(
            "Docling klarte ikke å lese Excel-filen.",
            details={"path": str(file_path), "error": str(exc)},
        ) from exc

    markdown_text = result.document.export_to_markdown()
    page_count = len(result.document.pages) if hasattr(result.document, "pages") else 1

    log.info("docling_conversion_done", page_count=page_count, text_length=len(markdown_text))  # type: ignore[attr-defined]
    return ParsedDocument(
        text=markdown_text,
        method=ParserMethod.SPREADSHEET,
        page_count=page_count,
        file_type=SourceFileType.XLSX,
        pages=[],
        ocr_pages=0,
    )


def _extract_image(file_path: Path, log: object) -> ParsedDocument:
    """Les et PNG/JPEG-bilde med GPT-4o Vision (primær) eller Docling EasyOCR (fallback).

    GPT-4o Vision brukes som primær metode fordi den produserer vesentlig bedre
    strukturert Markdown for multi-kolonne fakturaer enn EasyOCR + Doclings
    tabelleksport. EasyOCR slår kolonnestruktur (Consignor / Consignee) sammen
    til én uleselig blob, mens Vision bevarer seksjoner som ## Consignor osv.

    Fallback til EasyOCR skjer automatisk hvis OPENAI_API_KEY mangler eller
    Vision-kallet feiler.
    """
    settings = get_settings()
    api_key = settings.openai_api_key_value

    if api_key:
        try:
            from app.parsers.vision_parser import transcribe_image_with_vision  # lazy import

            log.info(  # type: ignore[attr-defined]
                "docling_image_vision_transcription_started",
                model=settings.docling_vlm_model,
            )
            markdown_text = transcribe_image_with_vision(
                file_path,
                api_key=api_key,
                model=settings.docling_vlm_model,
            )
            log.info(  # type: ignore[attr-defined]
                "docling_image_vision_transcription_done",
                text_length=len(markdown_text),
            )
            return ParsedDocument(
                text=markdown_text,
                method=ParserMethod.OCR,
                page_count=1,
                file_type=SourceFileType.IMAGE,
                pages=[],
                ocr_pages=1,
            )
        except Exception as exc:
            log.warning(  # type: ignore[attr-defined]
                "vision_transcription_failed_falling_back_to_easyocr",
                error=str(exc),
            )

    # Fallback — EasyOCR via Docling med GPU-støtte hvis tilgjengelig.
    try:
        log.info("docling_image_easyocr_started")  # type: ignore[attr-defined]
        result = _get_image_converter().convert(str(file_path))
    except Exception as exc:
        raise ParsingError(
            "Docling klarte ikke å lese bildefilen.",
            details={"path": str(file_path), "error": str(exc)},
        ) from exc

    markdown_text = result.document.export_to_markdown()
    page_count = len(result.document.pages) if hasattr(result.document, "pages") else 1

    log.info("docling_conversion_done", page_count=page_count, text_length=len(markdown_text))  # type: ignore[attr-defined]
    return ParsedDocument(
        text=markdown_text,
        method=ParserMethod.OCR,
        page_count=page_count,
        file_type=SourceFileType.IMAGE,
        pages=[],
        ocr_pages=page_count,
    )


def reset_converters() -> None:
    """Nullstill cached konvertere. Brukes i tester for å tvinge re-initialisering."""
    global _standard_converter, _multimodal_converter, _xlsx_converter, _image_converter
    _standard_converter = None
    _multimodal_converter = None
    _xlsx_converter = None
    _image_converter = None
