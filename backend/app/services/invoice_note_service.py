from __future__ import annotations

import re
from collections.abc import Iterable

from app.models.invoice import Invoice
from app.services.vat_check_service import evaluate_invoice_vat_mismatch

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

_FREE_MAIL_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "icloud.com",
    "protonmail.com",
    "live.com",
}

_GENERIC_NAME_TOKENS = {
    "the",
    "and",
    "group",
    "company",
    "technologies",
    "technology",
    "solutions",
    "services",
    "systems",
    "international",
    "holding",
    "holdings",
    "limited",
    "inc",
    "ltd",
    "llc",
    "plc",
    "as",
    "asa",
    "ag",
    "bv",
    "sa",
    "srl",
    "oy",
}


def _normalize_spaces(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _clip(value: str | None, max_len: int) -> str | None:
    text = _normalize_spaces(value)
    if not text:
        return None
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _extract_emails(raw_text: str | None, entity_emails: Iterable[str | None]) -> set[str]:
    out: set[str] = set()
    if raw_text:
        out.update(email.lower() for email in _EMAIL_RE.findall(raw_text.lower()))
    for email in entity_emails:
        if not email:
            continue
        m = _EMAIL_RE.search(email)
        if m:
            out.add(m.group(0).lower())
    return out


def _domain_tokens(domain: str) -> set[str]:
    out: set[str] = set()
    for part in re.split(r"[.\-]", domain.lower()):
        p = part.strip()
        if len(p) < 3:
            continue
        if p in {"com", "net", "org", "co", "io", "gov", "edu"}:
            continue
        out.add(p)
    return out


def _name_tokens(name: str | None) -> set[str]:
    if not name:
        return set()
    out: set[str] = set()
    for part in re.split(r"[^A-Za-z0-9]+", name.lower()):
        p = part.strip()
        if len(p) < 4:
            continue
        if p in _GENERIC_NAME_TOKENS:
            continue
        out.add(p)
    return out


def derive_vat_note(invoice: Invoice) -> tuple[str, str]:
    check = evaluate_invoice_vat_mismatch(invoice)
    comments = (invoice.comments or "").lower()

    if check.flagged:
        return "error", _clip(
            check.reason
            or "Mulig feilregistrert VAT ved eksport (regel + data indikerer avvik).",
            512,
        ) or "Mulig feilregistrert VAT ved eksport."

    llm_warn = (
        ("vat" in comments or "mva" in comments)
        and any(
            token in comments
            for token in (
                "mismatch",
                "incorrect",
                "wrong",
                "should be 0",
                "zero-rated",
                "vat exempt",
                "export",
            )
        )
    )

    if llm_warn:
        return "warn", "LLM peker på mulig VAT-avvik som bør verifiseres manuelt."

    if check.export_detected and not check.has_vat:
        return "ok", "Eksport indikert og ingen VAT funnet."

    return "ok", "Ingen tydelig VAT-avvik funnet."


def derive_email_note(invoice: Invoice) -> tuple[str, str]:
    entity_names = [entity.name for entity in invoice.entities]
    entity_tokens = set().union(*(_name_tokens(name) for name in entity_names)) if entity_names else set()
    emails = _extract_emails(invoice.raw_text, (entity.email for entity in invoice.entities))

    if not emails:
        return "ok", "Ingen e-post funnet i dokument/entiteter."

    matched_domains: set[str] = set()
    unmatched_domains: set[str] = set()
    free_domains: set[str] = set()
    all_domains: set[str] = set()

    for email in emails:
        if "@" not in email:
            continue
        domain = email.split("@", 1)[1].lower().strip()
        if not domain:
            continue
        all_domains.add(domain)
        if domain in _FREE_MAIL_DOMAINS:
            free_domains.add(domain)
        d_tokens = _domain_tokens(domain)
        if entity_tokens and d_tokens.intersection(entity_tokens):
            matched_domains.add(domain)
        else:
            unmatched_domains.add(domain)

    # Litt mer aggressiv modus:
    # Varsle tidligere ved avvik mellom domener og entitetsnavn.
    if free_domains and unmatched_domains:
        return "error", (
            "Free-mail + avvikende domener oppdaget "
            f"({', '.join(sorted((free_domains | unmatched_domains))[:3])})."
        )
    if free_domains:
        return "warn", f"Free-mail domene brukt ({', '.join(sorted(free_domains)[:2])})."
    if entity_tokens and unmatched_domains and not matched_domains:
        return "warn", (
            "E-postdomener matcher ikke identifiserte entiteter "
            f"({', '.join(sorted(unmatched_domains)[:2])})."
        )
    if len(unmatched_domains) >= 2:
        return "warn", (
            "Flere e-postdomener avviker fra entitetsnavn "
            f"({', '.join(sorted(unmatched_domains)[:2])})."
        )
    if unmatched_domains and matched_domains:
        return "warn", (
            "Minst ett e-postdomene avviker fra ellers konsistente domener "
            f"({', '.join(sorted(unmatched_domains)[:1])})."
        )
    if not entity_tokens and len(all_domains) >= 2:
        return "warn", "Flere ulike e-postdomener funnet uten tydelig entitetsmatch."
    if unmatched_domains and len(emails) >= 3:
        return "warn", (
            "Mange e-postadresser funnet, og minst ett domene avviker "
            f"({', '.join(sorted(unmatched_domains)[:1])})."
        )

    return "ok", "E-postdomener virker konsistente med identifiserte entiteter."


def derive_llm_note_preview(invoice: Invoice, max_len: int = 180) -> str | None:
    return _clip(invoice.comments, max_len)


def apply_invoice_notes(invoice: Invoice) -> None:
    vat_status, vat_text = derive_vat_note(invoice)
    email_status, email_text = derive_email_note(invoice)

    invoice.vat_note_status = vat_status
    invoice.vat_note_text = _clip(vat_text, 512)
    invoice.email_note_status = email_status
    invoice.email_note_text = _clip(email_text, 512)
    invoice.llm_note_preview = derive_llm_note_preview(invoice, max_len=180)
