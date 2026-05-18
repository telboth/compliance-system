"""
GPU-deteksjon — brukes av OCR-pipeline og Ollama-klient.

Resultat caches etter første kall: GPU-tilgjengelighet endres ikke i
løpet av en kjøring. Alle klienter kaller `get_gpu_info()` direkte —
ingen global init-kode utenfor funksjonen.

Støttede GPU-typer:
  CUDA — NVIDIA og AMD (via ROCm-bygget av torch)
  MPS  — Apple Silicon (M1/M2/M3/M4)
  CPU  — Fallback når ingen akselerator er tilgjengelig

Avhengighet:
  torch er valgfritt — hvis det ikke er installert returneres GpuInfo
  med available=False uten feilmelding. Docling installerer torch som
  avhengighet, så i produksjonsmiljø er det tilgjengelig.

Windows / OpenMP:
  Når EasyOCR og Docling lastes i samme prosess på Windows, kan begge
  forsøke å initialisere libiomp5md.dll (OpenMP-runtime), noe som gir
  «OMP: Error #15». KMP_DUPLICATE_LIB_OK=TRUE er standard workaround.
  Flagget settes her — før torch importeres — slik at det er effektivt
  uansett rekkefølge andre ML-biblioteker lastes inn.
"""

from __future__ import annotations

import os

# Windows-workaround: forhindre krasj ved dobbel OpenMP-initialisering.
# Settes KUN hvis ikke allerede definert (respekterer eksplisitt FALSE fra bruker).
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from dataclasses import dataclass
from functools import lru_cache

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GpuInfo:
    """Informasjon om tilgjengelig GPU-akselerator."""

    available: bool
    """True hvis en støttet GPU ble funnet og er klar til bruk."""

    device: str
    """'cuda', 'mps', eller 'cpu'."""

    name: str
    """Menneskelesbart GPU-navn, f.eks. 'NVIDIA GeForce RTX 4090' eller 'Apple Silicon (MPS)'."""

    vram_mb: int
    """VRAM i MiB — 0 for MPS (delt minne) og CPU."""


@lru_cache(maxsize=1)
def get_gpu_info() -> GpuInfo:
    """Detekter GPU-akselerator.  Resultatet caches — kaller kun torch én gang.

    Rekkefølge:
      1. CUDA  (NVIDIA, AMD via ROCm)
      2. MPS   (Apple Silicon)
      3. CPU   (fallback)

    Returns:
        GpuInfo med detaljer om tilgjengelig akselerator.
    """
    try:
        import torch
    except ImportError:
        logger.debug("gpu_detection_skipped", reason="torch er ikke installert")
        return GpuInfo(
            available=False,
            device="cpu",
            name="CPU (torch mangler)",
            vram_mb=0,
        )

    # ── NVIDIA / AMD via ROCm ──────────────────────────────────────────────────
    if torch.cuda.is_available():
        try:
            idx = torch.cuda.current_device()
            name = torch.cuda.get_device_name(idx)
            props = torch.cuda.get_device_properties(idx)
            vram_mb = props.total_memory // (1024 * 1024)
            logger.info(
                "gpu_detected",
                device="cuda",
                name=name,
                vram_mb=vram_mb,
                cuda_version=torch.version.cuda or "ukjent",
            )
            return GpuInfo(available=True, device="cuda", name=name, vram_mb=vram_mb)
        except Exception as exc:
            # cuda.is_available() kan gi True men init kan feile (f.eks. driver-mismatch)
            logger.warning("gpu_cuda_init_failed", error=str(exc))

    # ── Apple Silicon (MPS) ────────────────────────────────────────────────────
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        logger.info("gpu_detected", device="mps", name="Apple Silicon (MPS)", vram_mb=0)
        return GpuInfo(
            available=True,
            device="mps",
            name="Apple Silicon (MPS)",
            vram_mb=0,  # Delt minne med RAM — ikke mulig å hente størrelse
        )

    logger.info(
        "gpu_not_available",
        reason="Verken CUDA- eller MPS-akselerator er tilgjengelig — kjører på CPU",
    )
    return GpuInfo(available=False, device="cpu", name="CPU", vram_mb=0)
