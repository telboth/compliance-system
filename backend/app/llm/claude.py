"""
Anthropic Claude-klient for invoice-ekstraksjon.

Bruker Anthropic Python SDK med lazy import — SDK-en lastes kun første gang
extract_invoice() kalles, ikke ved API-oppstart.

Modell-valg:
  claude-sonnet-4-20250514  — anbefalt for ekstraksjon (rask, billig, god)
  claude-opus-4-7           — høyere presisjon, 5x dyrere

Structured output via system-prompt + JSON-validering. Vi bruker ikke
tool_use her fordi vi vil ha et enkelt JSON-svar vi kan parse direkte.
"""

from __future__ import annotations

from pathlib import Path

from app.core.errors import ApplicationError
from app.core.logging import get_logger
from app.llm.base import LLMClient
from app.llm.extraction import InvoiceExtractionResult
from app.llm.prompts import (
    INVOICE_EXTRACTION_SYSTEM,
    build_claude_vision_messages,
    build_extraction_messages,
)
from app.llm.response_parser import parse_llm_response

logger = get_logger(__name__)


class ClaudeClient(LLMClient):
    """LLM-klient som bruker Anthropic Claude via offisielt SDK."""

    def __init__(self, model_id: str, api_key: str) -> None:
        self._model_id = model_id
        self._api_key = api_key
        self._client = None  # Lazy — initialiseres ved første kall

    def _get_client(self):  # type: ignore[return]
        if self._client is None:
            from anthropic import AsyncAnthropic  # lazy import

            self._client = AsyncAnthropic(api_key=self._api_key)
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
            messages = build_claude_vision_messages(image_path, invoice_text)  # type: ignore[arg-type]
        else:
            messages = build_extraction_messages(invoice_text)  # type: ignore[assignment]

        try:
            logger.info(
                "claude_extraction_started",
                model=self._model_id,
                text_length=len(invoice_text),
                vision=using_vision,
            )
            response = await client.messages.create(
                model=self._model_id,
                max_tokens=4096,
                system=INVOICE_EXTRACTION_SYSTEM,
                messages=messages,  # type: ignore[arg-type]
                timeout=120,
            )
        except Exception as exc:
            raise ApplicationError(
                f"Anthropic API-kall feilet: {exc}",
                details={"model": self._model_id},
            ) from exc

        raw = response.content[0].text.strip()
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        logger.info(
            "claude_extraction_done",
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
