"""Invoice search endpoints (Elasticsearch-backed)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.security import ActorContext, require_roles
from app.schemas.search import (
    InvoiceSearchResponse,
    RAGSearchRequest,
    RAGSearchResponse,
    ReindexResponse,
    SearchFieldInfo,
    SearchFieldsResponse,
)
from app.services.invoice_rag_service import reindex_all_invoice_rag, search_invoice_rag
from app.services.invoice_search_service import reindex_all_invoices, search_invoices

router = APIRouter()


@router.get(
    "/fields",
    response_model=SearchFieldsResponse,
    summary="Vis tilgjengelige søkefelt",
)
async def get_search_fields() -> SearchFieldsResponse:
    return SearchFieldsResponse(
        global_search=SearchFieldInfo(
            key="q",
            label="Globalt søk",
            field_type="text",
            fuzzy=True,
            exact=False,
        ),
        fields=[
            SearchFieldInfo(
                key="entity_q",
                label="Entitet",
                field_type="text",
                fuzzy=True,
                exact=False,
            ),
            SearchFieldInfo(
                key="line_q",
                label="Varenavn / linjetekst",
                field_type="text",
                fuzzy=True,
                exact=False,
            ),
            SearchFieldInfo(
                key="serial_number",
                label="Serienummer",
                field_type="text",
                fuzzy=False,
                exact=True,
            ),
            SearchFieldInfo(
                key="destination_country",
                label="Destinasjonsland (ISO2)",
                field_type="keyword",
                fuzzy=False,
                exact=True,
            ),
        ],
    )


@router.get(
    "/invoices",
    response_model=InvoiceSearchResponse,
    summary="Søk i invoices, entiteter og varelinjer",
)
async def search_invoices_endpoint(
    q: str | None = Query(None, description="Globalt søk (fuzzy)."),
    entity_q: str | None = Query(None, description="Søk i entitetsnavn (fuzzy)."),
    line_q: str | None = Query(None, description="Søk i varelinjer/varenavn (fuzzy)."),
    serial_number: str | None = Query(None, description="Eksakt serienummer-søk."),
    destination_country: str | None = Query(None, description="Filtrer på destinasjonsland (ISO2)."),
    date_from: date | None = Query(None, description="Fakturadato fra og med."),
    date_to: date | None = Query(None, description="Fakturadato til og med."),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> InvoiceSearchResponse:
    return await search_invoices(
        q=q,
        entity_q=entity_q,
        line_q=line_q,
        serial_number=serial_number,
        destination_country=destination_country.upper().strip() if destination_country else None,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/reindex",
    response_model=ReindexResponse,
    summary="Reindekser alle invoices i Elasticsearch",
)
async def reindex_endpoint(
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> ReindexResponse:
    indexed, failed = await reindex_all_invoices()
    return ReindexResponse(
        message="Reindeksering fullført.",
        indexed=indexed,
        failed=failed,
    )


@router.post(
    "/rag/query",
    response_model=RAGSearchResponse,
    summary="Hybrid RAG-søk i invoice-tekst (BM25 + vector)",
)
async def rag_query_endpoint(body: RAGSearchRequest) -> RAGSearchResponse:
    if body.destination_country:
        body.destination_country = body.destination_country.upper().strip()
    return await search_invoice_rag(body)


@router.post(
    "/rag/reindex",
    response_model=ReindexResponse,
    summary="Reindekser RAG chunks for alle invoices",
)
async def rag_reindex_endpoint(
    _actor: ActorContext = Depends(require_roles("admin", "compliance_officer")),
) -> ReindexResponse:
    indexed_invoices, indexed_chunks, failed = await reindex_all_invoice_rag()
    return ReindexResponse(
        message=f"RAG reindeksering fullført. Chunks: {indexed_chunks}.",
        indexed=indexed_invoices,
        failed=failed,
    )
