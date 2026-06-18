"""
Fabrikk for LLM-klienter.

Brukes av extraction_service for å hente riktig klient basert på
valgt modell-ID. Støtter Anthropic, OpenAI og Ollama (OpenAI-compat.).
"""

from __future__ import annotations

from app.core.config import get_settings
from app.core.errors import ApplicationError
from app.core.logging import get_logger
from app.llm.base import LLMClient, LLMProvider

logger = get_logger(__name__)


def get_llm_client(model_id: str, provider: LLMProvider | None = None) -> LLMClient:
    """Returner en LLMClient for gitt modell.

    Args:
        model_id:  Modell-ID, f.eks. "claude-sonnet-4-20250514" eller "llama3.1:8b".
        provider:  Eksplisitt provider-override. Hvis None, detekteres fra model_id.

    Returns:
        En instans av ClaudeClient eller OpenAICompatibleClient.

    Raises:
        ApplicationError: Hvis nødvendig API-nøkkel mangler.
    """
    settings = get_settings()
    resolved_provider = provider or _detect_provider(model_id)

    if resolved_provider == LLMProvider.ANTHROPIC:
        api_key = settings.anthropic_api_key_value
        if not api_key:
            raise ApplicationError(
                "ANTHROPIC_API_KEY mangler i .secrets — kan ikke bruke Claude.",
                details={"model": model_id},
            )
        from app.llm.claude import ClaudeClient

        return ClaudeClient(model_id=model_id, api_key=api_key)

    if resolved_provider == LLMProvider.OPENAI:
        api_key = settings.openai_api_key_value
        if not api_key:
            raise ApplicationError(
                "OPENAI_API_KEY mangler i .secrets — kan ikke bruke OpenAI.",
                details={"model": model_id},
            )
        from app.llm.openai_client import OpenAICompatibleClient

        return OpenAICompatibleClient(model_id=model_id, api_key=api_key)

    if resolved_provider == LLMProvider.OLLAMA:
        from app.core.gpu import get_gpu_info
        from app.llm.openai_client import OpenAICompatibleClient

        ollama_url = f"{settings.ollama_base_url}/v1"
        gpu = get_gpu_info()

        # Bestem num_gpu-verdi:
        #   None (auto)  + GPU tilgjengelig → -1  (alle lag til GPU)
        #   None (auto)  + ingen GPU        → ikke send alternativet
        #   True (tving) → -1
        #   False (CPU)  →  0
        num_gpu: int | None = _resolve_ollama_num_gpu(settings.ollama_use_gpu, gpu.available)

        extra_body: dict = {}
        if num_gpu is not None:
            extra_body = {"options": {"num_gpu": num_gpu}}
            logger.info(
                "ollama_gpu_configured",
                model=model_id,
                num_gpu=num_gpu,
                gpu_name=gpu.name,
            )
        else:
            logger.info("ollama_gpu_not_used", model=model_id, reason="Ingen GPU funnet")

        return OpenAICompatibleClient(
            model_id=model_id,
            api_key="ollama",
            base_url=ollama_url,
            extra_body=extra_body if extra_body else None,
        )

    raise ApplicationError(
        f"Ukjent LLM-provider: {resolved_provider}",
        details={"model": model_id},
    )


def _resolve_ollama_num_gpu(setting: bool | None, gpu_available: bool) -> int | None:
    """Oversett settings.ollama_use_gpu til Ollamás num_gpu-parameter.

    Returns:
        -1  → alle lag til GPU
         0  → CPU-only
        None → ikke send alternativet (Ollama velger selv)
    """
    if setting is True:
        return -1  # Tving GPU uavhengig av deteksjon
    if setting is False:
        return 0  # Tving CPU
    # Auto: bruk GPU hvis tilgjengelig, ellers la Ollama bestemme
    return -1 if gpu_available else None


def _detect_provider(model_id: str) -> LLMProvider:
    """Detekter provider fra modell-ID-prefikset."""
    m = model_id.lower()
    if m.startswith("claude"):
        return LLMProvider.ANTHROPIC
    if m.startswith(("gpt-", "o1", "o3", "o4")):
        return LLMProvider.OPENAI
    # Alt annet antas å være en Ollama-modell (llama3.1:8b, mistral, osv.)
    return LLMProvider.OLLAMA
