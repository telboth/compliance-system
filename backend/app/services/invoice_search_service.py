"""Elasticsearch-backed invoice search and indexing."""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import get_session_factory
from app.core.logging import get_logger
from app.models.invoice import Invoice
from app.schemas.search import InvoiceSearchHit, InvoiceSearchResponse
from app.services.invoice_service import get_invoice
from app.utils.email_utils import EMAIL_RE as EMAIL_REGEX

logger = get_logger(__name__)

INDEX_NAME = "invoice_search_v1"
ES_TIMEOUT_SECONDS = 20.0


def _es_base() -> str:
    return get_settings().elasticsearch_url.rstrip("/")


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    out = value.strip()
    return out or None


def _normalize_serial(value: str | None) -> str | None:
    value = _normalize_text(value)
    if value is None:
        return None
    return value.lower()


def _to_str_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _extract_emails(value: str | None) -> list[str]:
    if not value:
        return []
    return [m.group(0).strip().lower() for m in EMAIL_REGEX.finditer(value)]


def _email_parts(email: str) -> list[str]:
    if not email:
        return []
    lowered = email.lower().strip()
    local, _, domain = lowered.partition("@")
    parts: list[str] = [lowered]
    if local:
        parts.extend([p for p in re.split(r"[^a-z0-9]+", local) if len(p) >= 3])
    if domain:
        domain_main = domain.split(".")[0]
        if len(domain_main) >= 3:
            parts.append(domain_main)
    return parts


def _index_mapping() -> dict[str, Any]:
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
                "invoice_number": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "original_filename": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "status": {"type": "keyword"},
                "direction": {"type": "keyword"},
                "destination_country": {"type": "keyword"},
                "invoice_date": {"type": "date"},
                "total_amount": {"type": "keyword"},
                "currency": {"type": "keyword"},
                "po_number": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "comments": {"type": "text"},
                "instructions": {"type": "text"},
                "raw_text": {"type": "text"},
                "emails": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "email_tokens": {"type": "text"},
                "entities": {
                    "type": "nested",
                    "properties": {
                        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "role": {"type": "keyword"},
                        "entity_type": {"type": "keyword"},
                        "country": {"type": "keyword"},
                        "email": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                        "address": {"type": "text"},
                    },
                },
                "lines": {
                    "type": "nested",
                    "properties": {
                        "description": {"type": "text"},
                        "product_code": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}},
                        },
                        "hs_code": {"type": "keyword"},
                        "eccn": {"type": "keyword"},
                        "serial_number": {"type": "keyword"},
                        "serial_number_norm": {
                            "type": "keyword",
                            "normalizer": "lowercase_norm",
                        },
                        "model_number": {
                            "type": "text",
                            "fields": {"keyword": {"type": "keyword"}},
                        },
                        "country_of_origin": {"type": "keyword"},
                    },
                },
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
            "invoice_search_es_http_error",
            method=method,
            path=path,
            status=response.status_code,
            body=response.text[:400],
        )
        response.raise_for_status()
    return response


async def ensure_search_index() -> None:
    """Create index when missing (idempotent)."""
    exists = await _es_request(
        "HEAD",
        f"/{INDEX_NAME}",
        expected_statuses={200, 404},
    )
    if exists.status_code == 200:
        return
    await _es_request(
        "PUT",
        f"/{INDEX_NAME}",
        json_payload=_index_mapping(),
        expected_statuses={200},
    )
    logger.info("invoice_search_index_created", index=INDEX_NAME)


def _invoice_to_doc(invoice: Invoice) -> dict[str, Any]:
    emails: list[str] = []
    emails.extend(_extract_emails(invoice.raw_text))
    for entity in invoice.entities:
        value = _normalize_text(entity.email)
        if value:
            emails.append(value.lower())
    unique_emails = list(dict.fromkeys(emails))
    email_tokens: list[str] = []
    for email in unique_emails:
        email_tokens.extend(_email_parts(email))
    unique_email_tokens = list(dict.fromkeys(email_tokens))

    return {
        "invoice_id": str(invoice.id),
        "invoice_number": _normalize_text(invoice.invoice_number),
        "original_filename": _normalize_text(invoice.original_filename),
        "status": invoice.status.value if invoice.status else None,
        "direction": invoice.direction.value if invoice.direction else None,
        "destination_country": _normalize_text(invoice.destination_country),
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "total_amount": _to_str_decimal(invoice.total_amount),
        "currency": _normalize_text(invoice.currency),
        "po_number": _normalize_text(invoice.po_number),
        "comments": _normalize_text(invoice.comments),
        "instructions": _normalize_text(invoice.instructions),
        "raw_text": _normalize_text(invoice.raw_text),
        "emails": unique_emails,
        "email_tokens": unique_email_tokens,
        "entities": [
            {
                "name": _normalize_text(entity.name),
                "role": entity.role.value if entity.role else None,
                "entity_type": entity.entity_type.value if entity.entity_type else None,
                "country": _normalize_text(entity.country),
                "email": _normalize_text(entity.email),
                "address": _normalize_text(entity.address),
            }
            for entity in invoice.entities
        ],
        "lines": [
            {
                "description": _normalize_text(line.description),
                "product_code": _normalize_text(line.product_code),
                "hs_code": _normalize_text(line.hs_code),
                "eccn": _normalize_text(line.eccn),
                "serial_number": _normalize_text(line.serial_number),
                "serial_number_norm": _normalize_serial(line.serial_number),
                "model_number": _normalize_text(line.model_number),
                "country_of_origin": _normalize_text(line.country_of_origin),
            }
            for line in invoice.lines
        ],
    }


async def index_invoice(invoice_id: uuid.UUID) -> None:
    """Upsert one invoice document in Elasticsearch."""
    await ensure_search_index()
    async with get_session_factory()() as session:
        invoice = await get_invoice(session, invoice_id)
    doc = _invoice_to_doc(invoice)
    await _es_request(
        "PUT",
        f"/{INDEX_NAME}/_doc/{invoice_id}",
        json_payload=doc,
        expected_statuses={200, 201},
    )
    try:
        from app.services.invoice_rag_service import index_invoice_rag

        await index_invoice_rag(invoice_id)
    except Exception:
        logger.exception("invoice_rag_index_failed", invoice_id=str(invoice_id))


async def delete_invoice_document(invoice_id: uuid.UUID) -> None:
    await _es_request(
        "DELETE",
        f"/{INDEX_NAME}/_doc/{invoice_id}",
        expected_statuses={200, 404},
    )
    try:
        from app.services.invoice_rag_service import delete_invoice_rag

        await delete_invoice_rag(invoice_id)
    except Exception:
        logger.exception("invoice_rag_delete_failed", invoice_id=str(invoice_id))


async def reindex_all_invoices() -> tuple[int, int]:
    """Reindex all invoices from DB to Elasticsearch."""
    await ensure_search_index()
    indexed = 0
    failed = 0
    async with get_session_factory()() as session:
        ids_res = await session.execute(select(Invoice.id))
        invoice_ids = list(ids_res.scalars().all())

    for invoice_id in invoice_ids:
        try:
            await index_invoice(invoice_id)
            indexed += 1
        except Exception:
            failed += 1
            logger.exception("invoice_search_reindex_one_failed", invoice_id=str(invoice_id))
    return indexed, failed


def _build_search_query(
    *,
    q: str | None,
    entity_q: str | None,
    line_q: str | None,
    serial_number: str | None,
    destination_country: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    must: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []

    if q:
        must.append(
            {
                "bool": {
                    "should": [
                        {"term": {"invoice_number.keyword": {"value": q, "boost": 8}}},
                        {"term": {"po_number.keyword": {"value": q, "boost": 6}}},
                        {
                            "multi_match": {
                                "query": q,
                                "fields": [
                                    "invoice_number^4",
                                    "original_filename^2",
                                    "po_number^2",
                                    "comments",
                                    "instructions",
                                    "raw_text",
                                    "emails^3",
                                    "email_tokens^5",
                                ],
                                "fuzziness": "AUTO",
                            }
                        },
                        {
                            "nested": {
                                "path": "entities",
                                "query": {
                                    "match_phrase": {
                                        "entities.name": {
                                            "query": q,
                                            "boost": 7,
                                        }
                                    }
                                },
                                "inner_hits": {"name": "entities_global_phrase", "size": 3},
                            }
                        },
                        {
                            "nested": {
                                "path": "entities",
                                "query": {
                                    "multi_match": {
                                        "query": q,
                                        "fields": [
                                            "entities.name^3",
                                            "entities.email^3",
                                            "entities.address",
                                        ],
                                        "fuzziness": "AUTO",
                                    }
                                },
                                "inner_hits": {"name": "entities_global", "size": 3},
                            }
                        },
                        {
                            "nested": {
                                "path": "lines",
                                "query": {
                                    "multi_match": {
                                        "query": q,
                                        "fields": [
                                            "lines.description^3",
                                            "lines.model_number^2",
                                            "lines.product_code^2",
                                            "lines.hs_code",
                                            "lines.eccn",
                                        ],
                                        "fuzziness": "AUTO",
                                    }
                                },
                                "inner_hits": {"name": "lines_global", "size": 3},
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    if entity_q:
        must.append(
            {
                "bool": {
                    "should": [
                        {
                            "nested": {
                                "path": "entities",
                                "query": {
                                    "bool": {
                                        "should": [
                                            {
                                                "match_phrase": {
                                                    "entities.name": {
                                                        "query": entity_q,
                                                        "boost": 8,
                                                    }
                                                }
                                            },
                                            {
                                                "match": {
                                                    "entities.name": {
                                                        "query": entity_q,
                                                        "fuzziness": "AUTO",
                                                        "boost": 3,
                                                    }
                                                }
                                            },
                                            {
                                                "match": {
                                                    "entities.email": {
                                                        "query": entity_q,
                                                        "fuzziness": "AUTO",
                                                        "boost": 4,
                                                    }
                                                }
                                            },
                                        ],
                                        "minimum_should_match": 1,
                                    }
                                },
                                "inner_hits": {"name": "entities_field", "size": 5},
                            }
                        },
                        {
                            "match": {
                                "email_tokens": {
                                    "query": entity_q,
                                    "fuzziness": "AUTO",
                                    "boost": 6,
                                }
                            }
                        },
                        {
                            "match": {
                                "emails": {
                                    "query": entity_q,
                                    "fuzziness": "AUTO",
                                    "boost": 3,
                                }
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    if line_q:
        must.append(
            {
                "nested": {
                    "path": "lines",
                    "query": {
                        "bool": {
                            "should": [
                                {
                                    "multi_match": {
                                        "query": line_q,
                                        "fields": [
                                            "lines.description^3",
                                            "lines.model_number^2",
                                            "lines.product_code^2",
                                        ],
                                        "fuzziness": "AUTO",
                                        "boost": 3,
                                    }
                                },
                                {
                                    "match_phrase": {
                                        "lines.description": {
                                            "query": line_q,
                                            "boost": 7,
                                        }
                                    }
                                },
                                {
                                    "term": {
                                        "lines.product_code.keyword": {
                                            "value": line_q,
                                            "boost": 8,
                                        }
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                    "inner_hits": {"name": "lines_field", "size": 5},
                }
            }
        )

    if serial_number:
        must.append(
            {
                "nested": {
                    "path": "lines",
                    "query": {
                        "term": {
                            "lines.serial_number_norm": _normalize_serial(serial_number),
                        }
                    },
                    "inner_hits": {"name": "lines_serial", "size": 5},
                }
            }
        )

    if destination_country:
        filters.append({"term": {"destination_country": destination_country.upper()}})

    if date_from or date_to:
        range_payload: dict[str, Any] = {}
        if date_from:
            range_payload["gte"] = date_from.isoformat()
        if date_to:
            range_payload["lte"] = date_to.isoformat()
        filters.append({"range": {"invoice_date": range_payload}})

    bool_query: dict[str, Any] = {}
    if must:
        bool_query["must"] = must
    if filters:
        bool_query["filter"] = filters
    if not bool_query:
        bool_query["must"] = [{"match_all": {}}]

    return {
        "from": offset,
        "size": limit,
        "query": {"bool": bool_query},
        "sort": [
            {"_score": {"order": "desc"}},
            {"invoice_date": {"order": "desc", "missing": "_last"}},
        ],
        "highlight": {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fields": {
                "comments": {},
                "instructions": {},
                "raw_text": {},
                "emails": {},
                "entities.name": {},
                "lines.description": {},
                "lines.model_number": {},
                "lines.product_code": {},
            },
            "fragment_size": 180,
            "number_of_fragments": 2,
        },
    }


def _extract_inner_hits(source: dict[str, Any], path: str, field: str) -> list[str]:
    out: list[str] = []
    inner_hits = source.get("inner_hits") or {}
    for name, path_block in inner_hits.items():
        if not isinstance(name, str) or not name.startswith(path):
            continue
        hits = (path_block.get("hits") or {}).get("hits") or []
        for hit in hits:
            value = (hit.get("_source") or {}).get(field)
            if isinstance(value, str) and value.strip():
                out.append(value.strip())
    return list(dict.fromkeys(out))


def _field_label(field_name: str) -> str:
    mapping = {
        "comments": "LLM-notater",
        "instructions": "Instruksjoner",
        "raw_text": "Dokumenttekst",
        "emails": "E-post",
        "email_tokens": "E-post-token",
        "entities.name": "Entiteter",
        "lines.description": "Varelinjer",
        "lines.model_number": "Modellnummer",
        "lines.product_code": "Produktkode",
    }
    return mapping.get(field_name, field_name)


def _build_field_matches(highlight: dict[str, Any]) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for field, snippets in highlight.items():
        if not isinstance(snippets, list):
            continue
        clean_snippets = [s for s in snippets if isinstance(s, str)]
        if not clean_snippets:
            continue
        out.append(
            {
                "field": field,
                "label": _field_label(field),
                "snippets": clean_snippets[:2],
            }
        )
    return out


def _first_entity_by_role(src: dict[str, Any], role: str) -> str | None:
    entities = src.get("entities") or []
    if not isinstance(entities, list):
        return None
    for ent in entities:
        if not isinstance(ent, dict):
            continue
        if str(ent.get("role") or "").strip().lower() == role:
            name = ent.get("name")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return None


def _shipment_summary(src: dict[str, Any]) -> dict[str, object]:
    lines = src.get("lines") or []
    items: list[str] = []
    if isinstance(lines, list):
        for line in lines:
            if not isinstance(line, dict):
                continue
            description = line.get("description")
            product_code = line.get("product_code")
            value = None
            if isinstance(description, str) and description.strip():
                value = description.strip()
            elif isinstance(product_code, str) and product_code.strip():
                value = product_code.strip()
            if value:
                items.append(value)
            if len(items) >= 3:
                break

    return {
        "consignor": _first_entity_by_role(src, "consignor"),
        "consignee": _first_entity_by_role(src, "consignee"),
        "end_user": _first_entity_by_role(src, "end_user"),
        "destination_country": src.get("destination_country"),
        "top_items": items,
    }


async def search_invoices(
    *,
    q: str | None = None,
    entity_q: str | None = None,
    line_q: str | None = None,
    serial_number: str | None = None,
    destination_country: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> InvoiceSearchResponse:
    await ensure_search_index()
    payload = _build_search_query(
        q=q,
        entity_q=entity_q,
        line_q=line_q,
        serial_number=serial_number,
        destination_country=destination_country,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    response = await _es_request(
        "POST",
        f"/{INDEX_NAME}/_search",
        json_payload=payload,
        expected_statuses={200},
    )
    raw = response.json()
    hits_raw = (raw.get("hits") or {}).get("hits") or []
    total_raw = (raw.get("hits") or {}).get("total") or {}
    total = int(total_raw.get("value") or 0) if isinstance(total_raw, dict) else int(total_raw or 0)
    took_ms = raw.get("took")

    hits: list[InvoiceSearchHit] = []
    for row in hits_raw:
        src = row.get("_source") or {}
        highlight = row.get("highlight") or {}
        highlights: list[str] = []
        for snippets in highlight.values():
            if isinstance(snippets, list):
                for snippet in snippets:
                    if isinstance(snippet, str):
                        highlights.append(snippet)

        hit = InvoiceSearchHit(
            invoice_id=str(src.get("invoice_id") or ""),
            score=float(row.get("_score") or 0.0),
            invoice_number=src.get("invoice_number"),
            original_filename=src.get("original_filename"),
            status=src.get("status"),
            direction=src.get("direction"),
            destination_country=src.get("destination_country"),
            invoice_date=src.get("invoice_date"),
            total_amount=src.get("total_amount"),
            currency=src.get("currency"),
            matched_entities=_extract_inner_hits(row, "entities", "name"),
            matched_lines=_extract_inner_hits(row, "lines", "description"),
            highlights=highlights[:4],
            field_matches=_build_field_matches(highlight),
            shipment_summary=_shipment_summary(src),
        )
        hits.append(hit)

    query_mode = (
        "structured" if any([entity_q, line_q, serial_number, destination_country, date_from, date_to]) else "global"
    )
    return InvoiceSearchResponse(
        total=total,
        limit=limit,
        offset=offset,
        took_ms=took_ms if isinstance(took_ms, int) else None,
        query_mode=query_mode,
        hits=hits,
    )
