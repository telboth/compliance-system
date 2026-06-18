"""Tester for RAG-hjelpefunksjoner (presisjon og evidence-gating)."""

from __future__ import annotations

from app.schemas.search import RAGSourceRef
from app.services.rag_utils import (
    build_term_focused_snippet,
    dedupe_scored_hits,
    normalized_snippet_for_key,
    query_terms,
    rag_hit_dedupe_key,
    select_answer_hits,
)


def _hit(*, chunk_id: str, snippet: str) -> RAGSourceRef:
    return RAGSourceRef(
        invoice_id="inv-1",
        chunk_id=chunk_id,
        original_filename="dummy.pdf",
        invoice_number="INV-001",
        chunk_index=0,
        score=1.0,
        snippet=snippet,
    )


def test_query_terms_keeps_signal_and_removes_noise() -> None:
    terms = query_terms("Er rosneft nevnt i noen invoice?")
    assert "rosneft" in terms
    assert "invoice" not in terms
    assert "nevnt" not in terms


def test_build_term_focused_snippet_centers_around_term() -> None:
    text = "Header text and generic invoice language. Contact: oleg.sanctionbuster@rosneft.com for notifications."
    snippet = build_term_focused_snippet(text, "rosneft", max_chars=80)
    assert "rosneft" in snippet.lower()
    assert len(snippet) <= 83  # max_chars + possible leading/trailing ellipsis


def test_select_answer_hits_requires_evidence_for_focus_terms() -> None:
    scored_hits = [
        (0, 10.0, _hit(chunk_id="c0", snippet="generic invoice text")),
        (0, 9.5, _hit(chunk_id="c1", snippet="more generic invoice text")),
    ]
    answer_hits, fallback = select_answer_hits(
        query="er rosneft nevnt i noen invoice?",
        focus_terms=["rosneft"],
        scored_hits=scored_hits,
    )
    assert answer_hits == []
    assert fallback is not None
    assert "rosneft" in fallback.lower()


def test_select_answer_hits_prefers_evidence_hits() -> None:
    scored_hits = [
        (0, 15.0, _hit(chunk_id="generic-top", snippet="invoice summary")),
        (1, 5.0, _hit(chunk_id="evidence", snippet="...@rosneft.com...")),
    ]
    answer_hits, fallback = select_answer_hits(
        query="rosneft",
        focus_terms=["rosneft"],
        scored_hits=scored_hits,
    )
    assert fallback is None
    assert len(answer_hits) == 1
    assert answer_hits[0].chunk_id == "evidence"


def test_normalized_snippet_for_key_removes_mark_tags() -> None:
    normalized = normalized_snippet_for_key("foo <mark>Rosneft</mark> bar")
    assert normalized == "foo rosneft bar"


def test_dedupe_scored_hits_keeps_strongest_duplicate() -> None:
    hit_a = _hit(chunk_id="a", snippet="Alpha <mark>Rosneft</mark> contact")
    hit_b = _hit(chunk_id="b", snippet="Alpha Rosneft contact")
    key_a = rag_hit_dedupe_key(hit_a)
    key_b = rag_hit_dedupe_key(hit_b)
    assert key_a == key_b

    deduped, removed = dedupe_scored_hits(
        [
            (0, 0.80, hit_a),
            (1, 0.70, hit_b),  # Høyere fokus-score skal vinne
        ]
    )
    assert len(deduped) == 1
    assert removed == 1
    assert deduped[0][2].chunk_id == "b"
