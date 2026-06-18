"""Tester for catch-all-/sluttbruker-screening.

Matchelogikken er ren (tar entiteter/linjer eksplisitt), så testene kjører uten
database.
"""

from __future__ import annotations

from app.models.entity import Entity, EntityRole, EntityType
from app.models.invoice import Invoice, InvoiceDirection, InvoiceStatus
from app.services.catch_all_service import evaluate_invoice_catch_all


def _invoice(destination: str | None, **kwargs) -> Invoice:
    base = {
        "direction": InvoiceDirection.OUTGOING,
        "pdf_path": "tests/fixtures/invoice.pdf",
        "status": InvoiceStatus.SCREENED,
        "destination_country": destination,
    }
    base.update(kwargs)
    return Invoice(**base)


def _end_user(name: str, country: str | None, role: EntityRole = EntityRole.END_USER) -> Entity:
    return Entity(
        name=name,
        entity_type=EntityType.COMPANY,
        country=country,
        role=role,
    )


def test_military_end_user_ordinary_country_is_review() -> None:
    inv = _invoice("IN")
    eu = _end_user("Ministry of Defence Procurement", "IN")
    res = evaluate_invoice_catch_all(inv, entities=[eu])
    assert res.status == "review"
    assert res.severity == "yellow"
    assert any(s.signal_type == "military_end_user" for s in res.signals)


def test_end_user_in_embargo_country_is_controlled() -> None:
    inv = _invoice("IR")
    eu = _end_user("Pars Industrial Group", "IR")
    res = evaluate_invoice_catch_all(inv, entities=[eu])
    assert res.status == "controlled"
    assert res.severity == "red"
    assert any(s.signal_type == "embargoed_end_user" for s in res.signals)


def test_sensitive_end_use_text_is_flagged() -> None:
    inv = _invoice("DE", instructions="Intended for naval application and missile guidance")
    eu = _end_user("Acme GmbH", "DE")
    res = evaluate_invoice_catch_all(inv, entities=[eu])
    assert res.flagged is True
    assert any(s.signal_type == "sensitive_end_use" for s in res.signals)


def test_broker_end_user_to_high_risk_is_diversion() -> None:
    inv = _invoice("RU")
    eu = _end_user("Global Logistics Forwarding", "RU")
    res = evaluate_invoice_catch_all(inv, entities=[eu])
    assert res.flagged is True
    assert any(s.signal_type == "diversion_risk" for s in res.signals)


def test_undeclared_end_user_to_embargo_country() -> None:
    inv = _invoice("KP")
    res = evaluate_invoice_catch_all(inv, entities=[])
    assert res.status == "controlled"  # KP comprehensive embargo
    assert any(s.signal_type == "undeclared_end_user" for s in res.signals)


def test_clean_invoice_is_clear() -> None:
    inv = _invoice("SE")
    eu = _end_user("Volvo AB", "SE")
    res = evaluate_invoice_catch_all(inv, entities=[eu])
    assert res.flagged is False
    assert res.status == "clear"
    assert res.severity == "green"
    assert res.signals == []


def test_consignee_used_when_no_end_user() -> None:
    inv = _invoice("IR")
    consignee = _end_user("Tehran Receiver Co", "IR", role=EntityRole.CONSIGNEE)
    res = evaluate_invoice_catch_all(inv, entities=[consignee])
    assert res.flagged is True
    assert res.end_user_country == "IR"
