"""Schemas for invoice search (Elasticsearch-backed)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator


class InvoiceSearchHit(BaseModel):
    invoice_id: str
    score: float
    invoice_number: str | None = None
    original_filename: str | None = None
    status: str | None = None
    direction: str | None = None
    destination_country: str | None = None
    invoice_date: date | None = None
    total_amount: str | None = None
    currency: str | None = None
    matched_entities: list[str] = Field(default_factory=list)
    matched_lines: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    field_matches: list[dict[str, object]] = Field(default_factory=list)
    shipment_summary: dict[str, object] = Field(default_factory=dict)


class InvoiceSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    took_ms: int | None = None
    query_mode: str
    hits: list[InvoiceSearchHit]


class SearchFieldInfo(BaseModel):
    key: str
    label: str
    field_type: str
    fuzzy: bool
    exact: bool = False


class SearchFieldsResponse(BaseModel):
    global_search: SearchFieldInfo
    fields: list[SearchFieldInfo]


class ReindexResponse(BaseModel):
    message: str
    indexed: int
    failed: int


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=2, description="Spørsmål eller søkefrase.")
    entity_q: str | None = None
    line_q: str | None = None
    serial_number: str | None = None
    destination_country: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = Field(default=10, ge=1, le=50)
    with_answer: bool = True

    @field_validator("query", mode="before")
    @classmethod
    def _normalize_query(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("entity_q", "line_q", "serial_number", "destination_country", mode="before")
    @classmethod
    def _empty_str_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def _empty_date_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class RAGSourceRef(BaseModel):
    invoice_id: str
    chunk_id: str
    original_filename: str | None = None
    invoice_number: str | None = None
    chunk_index: int
    score: float
    snippet: str
    evidence_hit: bool = True
    focus_match_count: int = 0


class RAGSearchResponse(BaseModel):
    query: str
    took_ms: int | None = None
    total: int
    total_raw: int
    total_after_dedupe: int
    answer: str | None = None
    answer_model: str | None = None
    answer_source_count: int = 0
    hits: list[RAGSourceRef] = Field(default_factory=list)
