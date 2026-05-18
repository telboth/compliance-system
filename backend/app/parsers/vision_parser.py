"""
Vision-basert OCR for bilde-fakturaer via GPT-4o.

Brukes som erstatning for Doclings EasyOCR når OPENAI_API_KEY er satt.
GPT-4o Vision gir vesentlig bedre strukturert tekst for multi-kolonne
fakturaer enn EasyOCR + Docling tabelleksport.

Funksjonen er synkron og kjøres inne i asyncio.run_in_executor() via
parse_invoice_in_background() — bruk aldri AsyncOpenAI her.
"""

from __future__ import annotations

import base64
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_MIME_TYPES: dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}

_TRANSCRIPTION_PROMPT = """\
Transcribe this trade document (commercial invoice, proforma invoice, packing list, or similar) \
as clean, structured Markdown.

FORMATTING RULES:
1. Use ## headers for every distinct section or party block. Use the label the document uses, e.g.:
   ## Consignor  (or ## Avsender, ## Sender, ## Expéditeur — whatever the document says)
   ## Consignee  (or ## Mottaker, ## Receiver, ## Destinataire)
   ## Notify Party
   ## Invoice Details   (invoice number, date, PO, payment terms, incoterms, currency, etc.)
   ## Transport         (mode, vessel/flight, port of loading/discharge)
   ## Line Items
   ## Instructions / Notes   (any free-text footer or notes section)

2. Under each party header, list contact fields as key: value lines, one per line:
   Company: Acme Corp
   Address: 12 Main Street, Oslo 0123, Norway
   Phone: +47 22 33 44 55
   Email: shipping@acme.no
   Contact: John Smith

3. Present line items as a Markdown table. Include whatever columns appear in the document
   (Description, Qty, Unit, Unit Price, Total, HS Code, ECCN, Country of Origin, \
Serial No., Model No., etc.).

4. Preserve ALL values exactly as written in the document — do not reformat, round, or
   normalise dates, amounts, currency codes, tariff codes, serial numbers, or reference IDs.

5. Include all visible text. Do not summarise, omit, or paraphrase any field.

6. Output ONLY the Markdown — no preamble, no explanation, no code fences.\
"""


def transcribe_image_with_vision(
    file_path: Path,
    api_key: str,
    model: str = "gpt-4o",
) -> str:
    """Kall GPT-4o Vision og returner strukturert Markdown-transkripsjon av bildet.

    Synkron — designet for kjøring inne i asyncio.run_in_executor().

    Args:
        file_path: Sti til PNG/JPEG/WEBP-filen.
        api_key:   OpenAI API-nøkkel.
        model:     Modell-ID (default gpt-4o).

    Returns:
        Ren Markdown-tekst som representerer dokumentets struktur og innhold.

    Raises:
        Exception: Propageres til kalleren — håndteres av docling_parser som fallback.
    """
    from openai import OpenAI  # lazy import — SDK lastes kun første gang

    ext = file_path.suffix.lstrip(".").lower()
    media_type = _MIME_TYPES.get(ext, "image/png")
    image_data = base64.b64encode(file_path.read_bytes()).decode()

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{image_data}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": _TRANSCRIPTION_PROMPT,
                    },
                ],
            }
        ],
        max_tokens=4096,
    )

    text: str = response.choices[0].message.content or ""
    logger.info(
        "vision_transcription_done",
        file=file_path.name,
        model=model,
        output_chars=len(text),
        input_tokens=response.usage.prompt_tokens if response.usage else 0,
        output_tokens=response.usage.completion_tokens if response.usage else 0,
    )
    return text
