"""
Ollama-klient — lokal LLM-kjøring.

Ollama eksponerer et OpenAI-kompatibelt API på /v1, så vi bruker openai-
pakken med custom base_url. Dette gir oss gratis: streaming, structured
output, og kompatibilitet med fremtidige OpenAI-modeller uten kodeendringer.

Ollama kjører som en systemtjeneste på maskinen til brukeren (port 11434).
Fra Docker-containere nås den via host.docker.internal:11434 på Windows/Mac.
"""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.base import LLMProvider, ModelInfo

logger = get_logger(__name__)


async def list_models() -> list[ModelInfo]:
    """Hent liste over tilgjengelige Ollama-modeller fra den lokale instansen.

    Returnerer tom liste (uten exception) hvis Ollama ikke er tilgjengelig —
    dette er forventet oppførsel på maskiner uten Ollama installert.
    """
    settings = get_settings()
    url = f"{settings.ollama_base_url}/api/tags"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.debug("ollama_unavailable", url=url, error=str(exc))
        return []

    models: list[ModelInfo] = []
    for m in data.get("models", []):
        name: str = m.get("name", "")
        # Ollama-modellnavn er typisk "llama3.1:8b" eller "mistral:latest".
        display = name.split(":")[0].replace("-", " ").title()
        models.append(
            ModelInfo(
                provider=LLMProvider.OLLAMA,
                model_id=name,
                display_name=f"{display} (lokal)",
                multimodal=_is_multimodal(name),
                local=True,
                tags=["ollama"],
            )
        )

    logger.debug("ollama_models_fetched", count=len(models))
    return models


def _is_multimodal(model_name: str) -> bool:
    """Grovt anslag på om modellen støtter bilde-input basert på navn."""
    multimodal_keywords = ("llava", "bakllava", "moondream", "vision", "minicpm-v")
    return any(kw in model_name.lower() for kw in multimodal_keywords)
