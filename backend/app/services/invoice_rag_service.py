"""Hybrid RAG search for invoices (BM25 + vector in Elasticsearch)."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.models.invoice import Invoice
from app.schemas.search import RAGSearchRequest, RAGSearchResponse, RAGSourceRef
from app.services.rag_utils import (
    WORD_RE,
    build_term_focused_snippet,
    count_focus_term_matches,
    dedupe_scored_hits,
    normalize,
    normalize_serial,
    pick_best_highlight_snippet,
    query_terms,
    select_answer_hits,
)

logger = get_logger(__name__)

RAG_INDEX_NAME = "invoice_rag_chunks_v1"
ES_TIMEOUT_SECONDS = 40.0
MAX_LLM_CONTEXT_CHARS = 10_000
_RULE_BASED_ANSWER_MODEL = "rule-based"


def _es_base() -> str:
    return get_settings().elasticsearch_url.rstrip("/")


def _index_mapping() -> dict[str, Any]:
    dims = int(get_settings().rag_embedding_dimensions or 1536)
    return {
        "settings": {
            "analysis": {
                "normalizer": {
                    "lowercase_norm": {
                        "type": "custom",
                        "filter": ["lowercase"],
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "invoice_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "chunk_index": {"type": "integer"},
                "chunk_text": {"type": "text"},
                "chunk_vector": {
                    "type": "dense_vector",
                    "dims": dims,
                    "index": True,
                    "similarity": "cosine",
                },
                "invoice_number": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "original_filename": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "status": {"type": "keyword"},
                "direction": {"type": "keyword"},
                "destination_country": {"type": "keyword"},
                "invoice_date": {"type": "date"},
                "entity_names": {"type": "text"},
                "entity_emails": {"type": "text"},
                "line_items": {"type": "text"},
                "serial_numbers_norm": {"type": "keyword", "normalizer": "lowercase_norm"},
            }
        },
    }


async def _es_request(
    method: str,
    path: str,
    *,
    json_payload: dict[str, Any] | None = None,
    expected_statuses: set[int] | None = None,
) -> httpx.Response:
    expected = expected_statuses or {200}
    url = f"{_es_base()}{path}"
    async with httpx.AsyncClient(timeout=ES_TIMEOUT_SECONDS) as client:
        response = await client.request(method, url, json=json_payload)
    if response.status_code not in expected:
        logger.warning(
            "invoice_rag_es_http_error",
            method=method,
            path=path,
            status=response.status_code,
            body=response.text[:500],
        )
        response.raise_for_status()
    return response


async def ensure_rag_index() -> None:
    exists = await _es_request(
        "HEAD",
        f"/{RAG_INDEX_NAME}",
        expected_statuses={200, 404},
    )
    if exists.status_code == 200:
        return
    response = await _es_request(
        "PUT",
        f"/{RAG_INDEX_NAME}",
        json_payload=_index_mapping(),
        expected_statuses={200, 400},
    )
    if response.status_code == 400:
        body = response.text
        if "resource_already_exists_exception" in body:
            return
        response.raise_for_status()
    logger.info("invoice_rag_index_created", index=RAG_INDEX_NAME)


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    clean = normalize(text) or ""
    if not clean:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", clean) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        chunk = "\n\n".join(current).strip()
        if chunk:
            chunks.append(chunk)
        if overlap <= 0 or not chunk:
            current = []
            current_len = 0
            return
        tail = chunk[-overlap:]
        current = [tail]
        current_len = len(tail)

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            parts = [
                paragraph[idx : idx + chunk_size]
                for idx in range(0, len(paragraph), chunk_size)
            ]
        else:
            parts = [paragraph]
        for part in parts:
            if current_len + len(part) + 2 > chunk_size and current:
                flush()
            current.append(part)
            current_len += len(part) + 2
    flush()
    return chunks


def _hashed_embedding(text: str, dims: int) -> list[float]:
    vec = [0.0] * dims
    for token in WORD_RE.findall(text.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if (digest[4] & 1) else -1.0
        weight = 1.0 + ((digest[5] % 7) / 10.0)
        vec[idx] += sign * weight
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    dims = int(settings.rag_embedding_dimensions or 1536)
    api_key = settings.openai_api_key_value
    if not api_key:
        return [_hashed_embedding(text, dims) for text in texts]

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key)
    model = settings.rag_embedding_model
    vectors: list[list[float]] = []
    batch_size = 48

    for idx in range(0, len(texts), batch_size):
        batch = texts[idx : idx + batch_size]
        response = await client.embeddings.create(
            model=model,
            input=batch,
            dimensions=dims,
            timeout=60,
        )
        vectors.extend([row.embedding for row in response.data])
    return vectors


def _build_invoice_corpus(invoice: Invoice) -> tuple[str, list[str], list[str], list[str]]:
    sections: list[str] = []
    if invoice.raw_text:
        sections.append(invoice.raw_text)

    entities: list[str] = []
    emails: list[str] = []
    for entity in invoice.entities:
        name = normalize(entity.name)
        if name:
            entities.append(name)
        email = normalize(entity.email)
        if email:
            emails.append(email.lower())
    if entities:
        sections.append("## Entities\n" + "\n".join(f"- {name}" for name in entities))
    if emails:
        sections.append("## Emails\n" + "\n".join(f"- {email}" for email in emails))

    line_items: list[str] = []
    serials: list[str] = []
    for line in invoice.lines:
        description = normalize(line.description)
        if description:
            line_items.append(description)
        serial = normalize_serial(line.serial_number)
        if serial:
            serials.append(serial)
    if line_items:
        sections.append("## Line items\n" + "\n".join(f"- {item}" for item in line_items))
    if serials:
        sections.append("## Serial numbers\n" + "\n".join(f"- {serial}" for serial in serials))

    corpus = "\n\n".join(part for part in sections if part.strip())
    return corpus, entities, emails, line_items


async def _fetch_invoice(invoice_id: uuid.UUID) -> Invoice:
    async with get_session_factory()() as session:
        stmt = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(selectinload(Invoice.entities), selectinload(Invoice.lines))
        )
        result = await session.execute(stmt)
        invoice = result.scalar_one_or_none()
    if invoice is None:
        raise ValueError(f"Invoice not found: {invoice_id}")
    return invoice


async def _delete_invoice_chunks(invoice_id: uuid.UUID) -> None:
    await _es_request(
        "POST",
        f"/{RAG_INDEX_NAME}/_delete_by_query",
        json_payload={"query": {"term": {"invoice_id": str(invoice_id)}}},
        expected_statuses={200},
    )


async def delete_invoice_rag(invoice_id: uuid.UUID) -> None:
    await ensure_rag_index()
    await _delete_invoice_chunks(invoice_id)


async def _bulk_index_docs(docs: list[dict[str, Any]]) -> None:
    if not docs:
        return
    lines: list[str] = []
    for doc in docs:
        lines.append('{"index":{}}')
        lines.append(json.dumps(doc, ensure_ascii=False))
    payload = ("\n".join(lines) + "\n").encode("utf-8")

    url = f"{_es_base()}/{RAG_INDEX_NAME}/_bulk"
    async with httpx.AsyncClient(timeout=ES_TIMEOUT_SECONDS) as client:
        response = await client.post(
            url,
            content=payload,
            headers={"Content-Type": "application/x-ndjson"},
        )
    if response.status_code != 200:
        logger.warning(
            "invoice_rag_es_bulk_failed",
            status=response.status_code,
            body=response.text[:500],
        )
        response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        logger.warning("invoice_rag_es_bulk_has_errors")


async def index_invoice_rag(invoice_id: uuid.UUID) -> int:
    started = time.perf_counter()
    await ensure_rag_index()
    invoice = await _fetch_invoice(invoice_id)
    corpus, entities, emails, line_items = _build_invoice_corpus(invoice)
    settings = get_settings()
    chunks = _chunk_text(
        corpus,
        chunk_size=max(300, int(settings.rag_chunk_size_chars or 1000)),
        overlap=max(0, int(settings.rag_chunk_overlap_chars or 150)),
    )

    await _delete_invoice_chunks(invoice_id)
    if not chunks:
        logger.info("invoice_rag_indexed", invoice_id=str(invoice_id), chunks=0, elapsed_ms=0)
        return 0

    vectors = await _embed_texts(chunks)
    serials_raw: list[str] = []
    for line in invoice.lines:
        serial_norm = normalize_serial(line.serial_number)
        if serial_norm:
            serials_raw.append(serial_norm)
    serials = list(dict.fromkeys(serials_raw))

    docs: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        docs.append(
            {
                "invoice_id": str(invoice.id),
                "chunk_id": f"{invoice.id}:{idx}",
                "chunk_index": idx,
                "chunk_text": chunk,
                "chunk_vector": vectors[idx],
                "invoice_number": normalize(invoice.invoice_number),
                "original_filename": normalize(invoice.original_filename),
                "status": invoice.status.value if invoice.status else None,
                "direction": invoice.direction.value if invoice.direction else None,
                "destination_country": normalize(invoice.destination_country),
                "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
                "entity_names": entities,
                "entity_emails": emails,
                "line_items": line_items,
                "serial_numbers_norm": serials,
            }
        )

    await _bulk_index_docs(docs)
    logger.info(
        "invoice_rag_indexed",
        invoice_id=str(invoice_id),
        chunks=len(docs),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
    return len(docs)


async def reindex_all_invoice_rag() -> tuple[int, int, int]:
    started = time.perf_counter()
    await ensure_rag_index()
    indexed_invoices = 0
    indexed_chunks = 0
    failed = 0

    async with get_session_factory()() as session:
        result = await session.execute(select(Invoice.id))
        invoice_ids = list(result.scalars().all())

    for invoice_id in invoice_ids:
        try:
            chunks = await index_invoice_rag(invoice_id)
            indexed_invoices += 1
            indexed_chunks += chunks
        except Exception:
            failed += 1
            logger.exception("invoice_rag_reindex_failed", invoice_id=str(invoice_id))
    logger.info(
        "invoice_rag_reindex_finished",
        invoices=indexed_invoices,
        chunks=indexed_chunks,
        failed=failed,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )
    return indexed_invoices, indexed_chunks, failed


def _build_bm25_query(body: RAGSearchRequest) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    must: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []
    focus_terms = query_terms(body.query)

    must.append(
        {
            "multi_match": {
                "query": body.query,
                "fields": [
                    "chunk_text^5",
                    "entity_names^4",
                    "line_items^3",
                    "entity_emails^3",
                    "invoice_number^2",
                    "original_filename^2",
                ],
                "fuzziness": "AUTO",
            }
        }
    )
    if focus_terms:
        must.append(
            {
                "multi_match": {
                    "query": " ".join(focus_terms[:6]),
                    "fields": [
                        "chunk_text^8",
                        "entity_emails^8",
                        "entity_names^6",
                        "line_items^4",
                    ],
                    "operator": "or",
                }
            }
        )

    if body.entity_q:
        must.append(
            {
                "multi_match": {
                    "query": body.entity_q,
                    "fields": ["entity_names^4", "entity_emails^3", "chunk_text^2"],
                    "fuzziness": "AUTO",
                }
            }
        )
    if body.line_q:
        must.append(
            {
                "multi_match": {
                    "query": body.line_q,
                    "fields": ["line_items^4", "chunk_text^2"],
                    "fuzziness": "AUTO",
                }
            }
        )
    if body.serial_number:
        filters.append({"term": {"serial_numbers_norm": normalize_serial(body.serial_number)}})
    if body.destination_country:
        filters.append({"term": {"destination_country": body.destination_country.upper().strip()}})
    if body.date_from or body.date_to:
        date_range: dict[str, Any] = {}
        if body.date_from:
            date_range["gte"] = body.date_from.isoformat()
        if body.date_to:
            date_range["lte"] = body.date_to.isoformat()
        filters.append({"range": {"invoice_date": date_range}})

    query = {"bool": {"must": must}}
    if filters:
        query["bool"]["filter"] = filters
    return query, filters


async def _build_answer(query: str, hits: list[RAGSourceRef]) -> tuple[str | None, str | None]:
    settings = get_settings()
    api_key = settings.openai_api_key_value
    if not api_key or not hits:
        return None, None

    from openai import AsyncOpenAI

    context_parts: list[str] = []
    total_chars = 0
    for idx, hit in enumerate(hits[:8], start=1):
        block = (
            f"[Source {idx}] invoice={hit.original_filename or hit.invoice_id}, "
            f"chunk={hit.chunk_index}\n{hit.snippet}\n"
        )
        if total_chars + len(block) > MAX_LLM_CONTEXT_CHARS:
            break
        context_parts.append(block)
        total_chars += len(block)
    if not context_parts:
        return None, None

    prompt = (
        "Svar kort på norsk. Bruk kun kildene under. "
        "En mention i e-postadresse/domene teller som nevnelse. "
        "Hvis evidens er svak, si det tydelig.\n\n"
        f"Spørsmål: {query}\n\n"
        "Kilder:\n"
        + "\n".join(context_parts)
    )

    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=settings.rag_llm_model,
        messages=[
            {
                "role": "system",
                "content": "Du er en compliance-analytiker som ikke finner på fakta.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=350,
        timeout=max(10, int(settings.rag_llm_timeout_seconds or 45)),
    )
    text = (response.choices[0].message.content or "").strip() or None
    return text, settings.rag_llm_model


def _query_fingerprint(query: str) -> str:
    return hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]


async def search_invoice_rag(body: RAGSearchRequest) -> RAGSearchResponse:
    started = time.perf_counter()
    query_fp = _query_fingerprint(body.query)
    logger.info(
        "invoice_rag_search_started",
        query_fp=query_fp,
        with_answer=body.with_answer,
        limit=body.limit,
    )
    await ensure_rag_index()
    bm25_query, filters = _build_bm25_query(body)
    limit = body.limit
    focus_terms = query_terms(body.query)

    payload: dict[str, Any] = {
        "size": limit,
        "_source": [
            "invoice_id",
            "chunk_id",
            "chunk_index",
            "chunk_text",
            "invoice_number",
            "original_filename",
            "destination_country",
            "invoice_date",
        ],
        "query": bm25_query,
        "highlight": {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fields": {"chunk_text": {"fragment_size": 240, "number_of_fragments": 2}},
        },
    }

    # Hybrid: kombiner BM25 med kNN hvis embedding er tilgjengelig.
    try:
        query_vector = (await _embed_texts([body.query]))[0]
        knn_payload: dict[str, Any] = {
            "field": "chunk_vector",
            "query_vector": query_vector,
            "k": max(limit * 4, 20),
            "num_candidates": max(limit * 10, 80),
            "boost": 1.2,
        }
        if filters:
            knn_payload["filter"] = filters
        payload["knn"] = knn_payload
    except Exception:
        logger.exception("invoice_rag_knn_disabled_fallback_bm25")

    response = await _es_request(
        "POST",
        f"/{RAG_INDEX_NAME}/_search",
        json_payload=payload,
        expected_statuses={200},
    )
    raw = response.json()
    took_ms = raw.get("took")
    rows = ((raw.get("hits") or {}).get("hits") or [])

    scored_hits: list[tuple[int, float, RAGSourceRef]] = []
    for row in rows:
        src = row.get("_source") or {}
        highlight = row.get("highlight") or {}
        snippets = highlight.get("chunk_text") or []
        snippet = ""
        if isinstance(snippets, list) and snippets:
            normalized_snippets = [str(s) for s in snippets if isinstance(s, str)]
            chosen = pick_best_highlight_snippet(
                normalized_snippets,
                body.query,
                focus_terms=focus_terms,
            )
            if chosen:
                snippet = chosen
        if not snippet:
            snippet = build_term_focused_snippet(
                str(src.get("chunk_text") or ""),
                body.query,
                max_chars=360,
                focus_terms=focus_terms,
            )
        score = float(row.get("_score") or 0.0)
        focus_matches = count_focus_term_matches(
            str(src.get("chunk_text") or ""),
            body.query,
            focus_terms=focus_terms,
        )
        hit = RAGSourceRef(
            invoice_id=str(src.get("invoice_id") or ""),
            chunk_id=str(src.get("chunk_id") or ""),
            original_filename=src.get("original_filename"),
            invoice_number=src.get("invoice_number"),
            chunk_index=int(src.get("chunk_index") or 0),
            score=score,
            snippet=snippet,
            evidence_hit=focus_matches > 0 if focus_terms else True,
            focus_match_count=focus_matches,
        )
        scored_hits.append((focus_matches, score, hit))

    deduped_scored_hits, deduped_removed = dedupe_scored_hits(scored_hits)
    if deduped_removed > 0:
        logger.info(
            "invoice_rag_hits_deduped",
            query_fp=query_fp,
            original=len(scored_hits),
            deduped=len(deduped_scored_hits),
            removed=deduped_removed,
        )
    deduped_scored_hits.sort(key=lambda row: (row[0], row[1]), reverse=True)
    hits = [row[2] for row in deduped_scored_hits[:limit]]

    answer: str | None = None
    answer_model: str | None = None
    if body.with_answer:
        answer_hits, fallback_answer = select_answer_hits(
            query=body.query,
            focus_terms=focus_terms,
            scored_hits=deduped_scored_hits[:limit],
        )
        if fallback_answer is not None:
            answer = fallback_answer
            answer_model = _RULE_BASED_ANSWER_MODEL
        elif answer_hits:
            try:
                answer, answer_model = await _build_answer(body.query, answer_hits)
            except Exception:
                logger.exception("invoice_rag_answer_generation_failed")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "invoice_rag_search_finished",
        query_fp=query_fp,
        took_ms=took_ms if isinstance(took_ms, int) else None,
        total_raw=len(scored_hits),
        total_after_dedupe=len(deduped_scored_hits),
        returned_hits=len(hits),
        elapsed_ms=elapsed_ms,
    )

    return RAGSearchResponse(
        query=body.query,
        took_ms=took_ms if isinstance(took_ms, int) else None,
        total=len(deduped_scored_hits),
        total_raw=len(scored_hits),
        total_after_dedupe=len(deduped_scored_hits),
        answer=answer,
        answer_model=answer_model,
        answer_source_count=min(len(hits), 8),
        hits=hits,
    )
