"""Tester for modell-discovery API."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.llm.base import LLMProvider, ModelInfo


@pytest.mark.asyncio
async def test_models_returns_providers(client: AsyncClient) -> None:
    ollama_model = ModelInfo(
        provider=LLMProvider.OLLAMA,
        model_id="mistral:latest",
        display_name="Mistral (lokal)",
        local=True,
    )
    with patch(
        "app.api.v1.models.list_ollama_models",
        new=AsyncMock(return_value=[ollama_model]),
    ):
        response = await client.get("/api/v1/models")

    assert response.status_code == 200
    body = response.json()
    provider_ids = [p["provider_id"] for p in body["providers"]]
    assert "anthropic" in provider_ids
    assert "openai" in provider_ids
    assert "ollama" in provider_ids


@pytest.mark.asyncio
async def test_models_ollama_unavailable_returns_empty(client: AsyncClient) -> None:
    with patch(
        "app.api.v1.models.list_ollama_models",
        new=AsyncMock(return_value=[]),
    ):
        response = await client.get("/api/v1/models")

    assert response.status_code == 200
    ollama = next(p for p in response.json()["providers"] if p["provider_id"] == "ollama")
    assert ollama["available"] is False
    assert ollama["models"] == []
