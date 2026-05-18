"""
Delt parser for JSON-svar fra LLM-klienter.

Inneholder _strip_fences() og _parse_response() som brukes av både
ClaudeClient og OpenAICompatibleClient.  Separert hit for å unngå at
openai_client.py importerer private symboler fra claude.py.
"""

from __future__ import annotations

import json
import re

from app.core.errors import ApplicationError
from app.llm.extraction import (
    ExtractedEntity,
    ExtractedLine,
    FieldValue,
    InvoiceExtractionResult,
)


def strip_fences(raw: str) -> str:
    """Fjern markdown-kodefences fra LLM-svar.

    Noen modeller legger til ```json ... ``` selv om prompten sier de ikke skal.
    Funksjonen er idempotent — rå JSON uten fences returneres uendret.
    """
    stripped = raw.strip()
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", stripped, re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def parse_llm_response(
    raw: str,
    *,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    confidence_threshold: float,
) -> InvoiceExtractionResult:
    """Parser JSON-svaret fra en LLM-klient til InvoiceExtractionResult.

    Feiler grasiøst: ugyldige felter hoppes over, ikke tilstede felter
    får konfidens 0 og verdi None.
    """
    cleaned = strip_fences(raw)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ApplicationError(
            "LLM returnerte ugyldig JSON.",
            details={"raw_preview": cleaned[:500], "error": str(exc)},
        ) from exc

    def field_value(key: str) -> FieldValue:
        obj = data.get(key, {})
        if isinstance(obj, dict):
            return FieldValue(value=obj.get("value"), confidence=float(obj.get("confidence", 0.0)))
        return FieldValue(value=str(obj) if obj is not None else None, confidence=0.5)

    entities: list[ExtractedEntity] = []
    for e in data.get("entities", []):
        try:
            entities.append(ExtractedEntity(**e))
        except Exception:  # noqa: S110 — ugyldig entitet hoppes over med vilje
            pass

    lines: list[ExtractedLine] = []
    for line in data.get("lines", []):
        try:
            lines.append(ExtractedLine(**line))
        except Exception:  # noqa: S110 — ugyldig linje hoppes over med vilje
            pass

    result = InvoiceExtractionResult(
        invoice_number=field_value("invoice_number"),
        invoice_date=field_value("invoice_date"),
        total_amount=field_value("total_amount"),
        currency=field_value("currency"),
        incoterms=field_value("incoterms"),
        transport_mode=field_value("transport_mode"),
        destination_country=field_value("destination_country"),
        po_number=field_value("po_number"),
        comments=data.get("comments"),
        entities=entities,
        lines=lines,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model_id=model_id,
    )
    result.compute_derived(threshold=confidence_threshold)
    return result
