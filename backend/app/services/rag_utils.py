"""Utilities for invoice RAG relevance, snippets, and hit dedupe."""

from __future__ import annotations

import re

from app.schemas.search import RAGSourceRef

WORD_RE = re.compile(r"[a-z0-9][a-z0-9._-]{1,}", re.IGNORECASE)
WS_RE = re.compile(r"\s+")
_RAG_NOISE_TERMS = {
    "invoice",
    "invoices",
    "faktura",
    "fakturaer",
    "nevnt",
    "mentioned",
    "finnes",
    "findes",
    "sanksjon",
    "sanksjoner",
    "compliance",
    "hvor",
    "noen",
    "nokon",
    "nevnes",
    "nevner",
    "which",
    "som",
    "that",
    "with",
    "from",
}


def normalize(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = WS_RE.sub(" ", value).strip()
    return stripped or None


def normalize_serial(value: str | None) -> str | None:
    normalized = normalize(value)
    return normalized.lower() if normalized else None


def query_terms(query: str) -> list[str]:
    """Extract focus terms from query and remove noise words."""
    terms: list[str] = []
    seen: set[str] = set()
    for token in WORD_RE.findall(query.lower()):
        if len(token) < 4:
            continue
        if token in _RAG_NOISE_TERMS:
            continue
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)
    terms.sort(key=len, reverse=True)
    return terms


def build_term_focused_snippet(
    text: str,
    query: str,
    max_chars: int = 360,
    focus_terms: list[str] | None = None,
) -> str:
    """Build snippet around first relevant query term found in text."""
    raw = normalize(text) or ""
    if not raw:
        return ""

    lowered = raw.lower()
    terms = focus_terms if focus_terms is not None else query_terms(query)
    for term in terms:
        idx = lowered.find(term)
        if idx < 0:
            continue
        start = max(0, idx - (max_chars // 2))
        end = min(len(raw), start + max_chars)
        snippet = raw[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(raw):
            snippet = snippet + "..."
        return snippet

    return raw[:max_chars].strip()


def pick_best_highlight_snippet(
    snippets: list[str],
    query: str,
    focus_terms: list[str] | None = None,
) -> str | None:
    """Pick highlight fragment that contains relevant query terms when possible."""
    if not snippets:
        return None
    terms = focus_terms if focus_terms is not None else query_terms(query)
    if not terms:
        return snippets[0].strip() if snippets[0].strip() else None

    for snippet in snippets:
        lowered = snippet.lower()
        if any(term in lowered for term in terms):
            cleaned = snippet.strip()
            if cleaned:
                return cleaned

    cleaned_first = snippets[0].strip()
    return cleaned_first or None


def count_focus_term_matches(
    text: str,
    query: str,
    focus_terms: list[str] | None = None,
) -> int:
    """Count unique focus terms found in text."""
    lowered = text.lower()
    count = 0
    terms = focus_terms if focus_terms is not None else query_terms(query)
    for term in terms:
        if term in lowered:
            count += 1
    return count


def normalized_snippet_for_key(snippet: str) -> str:
    """Normalize snippet for stable dedupe key."""
    cleaned = snippet.replace("<mark>", "").replace("</mark>", "")
    normalized = normalize(cleaned) or ""
    return normalized.lower()


def rag_hit_dedupe_key(hit: RAGSourceRef) -> tuple[str, int, str]:
    """Semantic dedupe key for nearly-identical hits."""
    invoice_ref = (
        (normalize(hit.invoice_number) or "")
        or (normalize(hit.original_filename) or "")
        or hit.invoice_id
    ).lower()
    snippet_key = normalized_snippet_for_key(hit.snippet)[:220]
    return (invoice_ref, hit.chunk_index, snippet_key)


def dedupe_scored_hits(
    scored_hits: list[tuple[int, float, RAGSourceRef]],
) -> tuple[list[tuple[int, float, RAGSourceRef]], int]:
    """Deduplicate hits, keeping strongest variant per semantic key."""
    by_key: dict[tuple[str, int, str], tuple[int, float, RAGSourceRef]] = {}
    for row in scored_hits:
        key = rag_hit_dedupe_key(row[2])
        existing = by_key.get(key)
        if existing is None or (row[0], row[1]) > (existing[0], existing[1]):
            by_key[key] = row

    deduped = list(by_key.values())
    removed = len(scored_hits) - len(deduped)
    return deduped, removed


def no_evidence_answer(_query: str, focus_terms: list[str]) -> str:
    """Standard answer when no focus terms are found in evidence."""
    if focus_terms:
        if len(focus_terms) == 1:
            term_display = focus_terms[0]
        else:
            term_display = ", ".join(focus_terms[:3])
        return (
            "Ingen tydelige treff i RAG-kildene for soketermene: "
            f"{term_display}. Svar krever manuell verifisering."
        )
    return (
        "Ingen tydelige treff i RAG-kildene for foresporselen. "
        "Svar krever manuell verifisering."
    )


def select_answer_hits(
    *,
    query: str,
    focus_terms: list[str],
    scored_hits: list[tuple[int, float, RAGSourceRef]],
) -> tuple[list[RAGSourceRef], str | None]:
    """Pick hits for answer generation with explicit evidence gate."""
    if not scored_hits:
        return [], no_evidence_answer(query, focus_terms)

    if not focus_terms:
        return [row[2] for row in scored_hits[:8]], None

    evidence_hits = [row[2] for row in scored_hits if row[0] > 0]
    if evidence_hits:
        return evidence_hits[:8], None
    return [], no_evidence_answer(query, focus_terms)

