"""
Modell-discovery API.

Returnerer hvilke LLM-providers og modeller som er tilgjengelige. Frontenden
bruker dette til å populere modellvelgeren. Ollama-modeller hentes dynamisk
fra den lokale instansen; andre providers defineres statisk med tilgjengelighet
basert på om API-nøkkel er konfigurert.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.llm.base import LLMProvider, ModelInfo
from app.llm.ollama import list_models as list_ollama_models

router = APIRouter()


class ModelResponse(BaseModel):
    provider: str
    model_id: str
    display_name: str
    multimodal: bool
    local: bool
    available: bool
    tags: list[str]


class ProviderResponse(BaseModel):
    provider_id: str
    display_name: str
    available: bool
    models: list[ModelResponse]


class ModelsListResponse(BaseModel):
    providers: list[ProviderResponse]
    docling_pipeline: str


def _static_providers(settings) -> list[tuple[LLMProvider, list[ModelInfo]]]:
    """Definerer statiske (ikke-Ollama) providers og modeller."""
    anthropic_available = bool(settings.anthropic_api_key_value)
    openai_available = bool(settings.openai_api_key_value)

    return [
        (
            LLMProvider.ANTHROPIC,
            [
                ModelInfo(
                    provider=LLMProvider.ANTHROPIC,
                    model_id="claude-sonnet-4-6",
                    display_name="Claude Sonnet 4.6",
                    multimodal=True,
                    context_window=200_000,
                    tags=["recommended"],
                ),
                ModelInfo(
                    provider=LLMProvider.ANTHROPIC,
                    model_id="claude-opus-4-7",
                    display_name="Claude Opus 4.7",
                    multimodal=True,
                    context_window=200_000,
                    tags=["powerful"],
                ),
            ],
        ),
        (
            LLMProvider.OPENAI,
            [
                ModelInfo(
                    provider=LLMProvider.OPENAI,
                    model_id="gpt-4o",
                    display_name="GPT-4o",
                    multimodal=True,
                    context_window=128_000,
                    tags=["multimodal", "docling-vlm"],
                ),
                ModelInfo(
                    provider=LLMProvider.OPENAI,
                    model_id="gpt-4o-mini",
                    display_name="GPT-4o Mini",
                    multimodal=True,
                    context_window=128_000,
                    tags=["fast", "cheap"],
                ),
            ],
        ),
    ]


@router.get("/models", response_model=ModelsListResponse, summary="List tilgjengelige LLM-modeller")
async def list_models() -> ModelsListResponse:
    """Returnerer alle tilgjengelige LLM-providers og modeller.

    - Anthropic og OpenAI: statisk liste, `available` basert på API-nøkkel i .secrets.
    - Ollama: dynamisk hentet fra lokal instans (http://localhost:11434).
      Returnerer tom liste hvis Ollama ikke kjører — ingen feil.
    """
    settings = get_settings()
    anthropic_available = bool(settings.anthropic_api_key_value)
    openai_available = bool(settings.openai_api_key_value)

    availability = {
        LLMProvider.ANTHROPIC: anthropic_available,
        LLMProvider.OPENAI: openai_available,
    }
    display_names = {
        LLMProvider.ANTHROPIC: "Anthropic Claude",
        LLMProvider.OPENAI: "OpenAI",
    }

    providers: list[ProviderResponse] = []

    for provider, models in _static_providers(settings):
        providers.append(
            ProviderResponse(
                provider_id=provider.value,
                display_name=display_names[provider],
                available=availability[provider],
                models=[
                    ModelResponse(
                        provider=provider.value,
                        model_id=m.model_id,
                        display_name=m.display_name,
                        multimodal=m.multimodal,
                        local=False,
                        available=availability[provider],
                        tags=list(m.tags),
                    )
                    for m in models
                ],
            )
        )

    ollama_models = await list_ollama_models()
    providers.append(
        ProviderResponse(
            provider_id=LLMProvider.OLLAMA.value,
            display_name="Ollama (lokal)",
            available=len(ollama_models) > 0,
            models=[
                ModelResponse(
                    provider=LLMProvider.OLLAMA.value,
                    model_id=m.model_id,
                    display_name=m.display_name,
                    multimodal=m.multimodal,
                    local=True,
                    available=True,
                    tags=list(m.tags),
                )
                for m in ollama_models
            ],
        )
    )

    return ModelsListResponse(
        providers=providers,
        docling_pipeline=settings.docling_pipeline,
    )
