"""
OpenAI-kompatibel klient — brukes for OpenAI og Ollama.

Ollama eksponerer et OpenAI-kompatibelt API (/v1/chat/completions), så
den samme klienten kan nå begge ved å sette base_url og api_key.

For Ollama settes api_key til "ollama" (SDK krever en streng, men Ollama
validerer den ikke). base_url peker på host.docker.internal:11434/v1 fra
Docker-containere, eller localhost:11434/v1 fra lokal prosess.

JSON-parsing er identisk med claude.py — se den filen for kommentarer.
"""

from __future__ import annotations

from pathlib import Path

from app.core.errors import ApplicationError
from app.core.logging import get_logger
from app.llm.base import LLMClient
from app.llm.extraction import InvoiceExtractionResult
from app.llm.prompts import (
    INVOICE_EXTRACTION_SYSTEM,
    build_extraction_messages,
    build_openai_vision_messages,
)
from app.llm.response_parser import parse_llm_response

logger = get_logger(__name__)


class OpenAICompatibleClient(LLMClient):
    """LLM-klient for OpenAI og Ollama via openai Python SDK."""

    def __init__(
        self,
        model_id: str,
        api_key: str,
        base_url: str | None = None,
        extra_body: dict | None = None,
    ) -> None:
        self._model_id = model_id
        self._api_key = api_key
        self._base_url = base_url
        # extra_body sendes til API-et i tillegg til standard parametere.
        # For Ollama kan dette inneholde {"options": {"num_gpu": -1}} for GPU-kjøring.
        self._extra_body = extra_body or {}
        self._client = None  # Lazy

    def _get_client(self):  # type: ignore[return]
        if self._client is None:
            from openai import AsyncOpenAI  # lazy import

            kwargs: dict = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = AsyncOpenAI(**kwargs)
        return self._client

    async def extract_invoice(
        self,
        invoice_text: str,
        *,
        image_path: Path | None = None,
        confidence_threshold: float = 0.8,
    ) -> InvoiceExtractionResult:
        client = self._get_client()

        using_vision = image_path is not None and image_path.exists()
        if using_vision:
            messages = build_openai_vision_messages(image_path, invoice_text)  # type: ignore[arg-type]
        else:
            messages = build_extraction_messages(invoice_text)  # type: ignore[assignment]

        try:
            logger.info(
                "openai_extraction_started",
                model=self._model_id,
                text_length=len(invoice_text),
                vision=using_vision,
            )
            response = await client.chat.completions.create(
                model=self._model_id,
                max_tokens=4096,
                messages=[
                    {"role": "system", "content": INVOICE_EXTRACTION_SYSTEM},
                    *messages,  # type: ignore[arg-type]
                ],
                response_format={"type": "json_object"},
                timeout=120,
                extra_body=self._extra_body if self._extra_body else None,
            )
        except Exception as exc:
            raise ApplicationError(
                f"OpenAI/Ollama API-kall feilet: {exc}",
                details={"model": self._model_id, "base_url": self._base_url},
            ) from exc

        raw = (response.choices[0].message.content or "").strip()
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        logger.info(
            "openai_extraction_done",
            model=self._model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return parse_llm_response(
            raw,
            model_id=self._model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            confidence_threshold=confidence_threshold,
        )
