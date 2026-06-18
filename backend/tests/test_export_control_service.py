"""Tester for eksportkontroll-listematch (DEKSA Vareliste I/II).

Matchelogikken er ren (tar fakturalinjer eksplisitt), så testene kjører uten
database.
"""

from __future__ import annotations

from app.data import export_control_reference as ref
from app.models.invoice import Invoice, InvoiceDirection, InvoiceStatus
from app.models.invoice_line import InvoiceLine
from app.services.export_control_service import (
    classify_code,
    evaluate_invoice_export_control,
)


def _invoice(destination: str | None) -> Invoice:
    return Invoice(
        direction=InvoiceDirection.OUTGOING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.SCREENED,
        destination_country=destination,
    )


def _line(**kwargs) -> InvoiceLine:
    base = {"description": None, "eccn": None, "hs_code": None}
    base.update(kwargs)
    return InvoiceLine(**base)


# ── Strukturell kodeparsing ───────────────────────────────────────────────────


def test_parse_dual_use_code() -> None:
    sm = ref.parse_control_code("6A001.a.2.a.6")
    assert sm is not None
    assert sm.list_code == "II"
    assert sm.category == "6"
    assert sm.group == "A"
    assert sm.normalized_code == "6A001"


def test_parse_military_code() -> None:
    sm = ref.parse_control_code("ML 10")
    assert sm is not None
    assert sm.list_code == "I"
    assert sm.category == "ML10"
    assert sm.group is None


def test_parse_rejects_hs_code() -> None:
    assert ref.parse_control_code("8517.12") is None
    assert ref.parse_control_code("Office chair") is None


def test_classify_code_returns_category_titles() -> None:
    result = classify_code("6A001")
    assert result is not None
    assert result["list_code"] == "II"
    assert result["category"] == "6"
    assert "ensor" in (result["category_title_no"] or "")  # "Sensorer og lasere"


# ── Faktura-evaluering ────────────────────────────────────────────────────────


def test_explicit_dual_use_ordinary_destination_is_review() -> None:
    inv = _invoice("DE")
    res = evaluate_invoice_export_control(inv, lines=[_line(description="Fiber gyroscope", eccn="6A001")])
    assert res.flagged is True
    assert res.status == "review"
    assert res.severity == "yellow"
    assert any(h.list_code == "II" and h.confidence == "high" for h in res.hits)


def test_explicit_dual_use_to_sanctioned_destination_is_controlled() -> None:
    inv = _invoice("IR")  # Iran — totalembargo
    res = evaluate_invoice_export_control(inv, lines=[_line(description="Crypto module", eccn="5A002")])
    assert res.status == "controlled"
    assert res.severity == "red"
    assert res.destination_sanctioned is True


def test_explicit_military_code_is_controlled_regardless_of_destination() -> None:
    inv = _invoice("SE")  # Sverige — vennligsinnet
    res = evaluate_invoice_export_control(inv, lines=[_line(description="Weapon sight", eccn="ML5")])
    assert res.status == "controlled"
    assert res.severity == "red"
    assert any(h.list_code == "I" for h in res.hits)


def test_keyword_only_match_is_review() -> None:
    inv = _invoice("US")
    res = evaluate_invoice_export_control(inv, lines=[_line(description="High power laser cutter")])
    assert res.flagged is True
    assert res.status == "review"
    assert all(h.confidence == "low" for h in res.hits if h.matched_via == "keyword")


def test_hs_bridge_controlled_chapter_is_flagged() -> None:
    inv = _invoice("FR")
    res = evaluate_invoice_export_control(inv, lines=[_line(description="navigation unit", hs_code="8526.10")])
    assert res.flagged is True
    assert any(h.matched_via == "hs" for h in res.hits)


def test_clean_invoice_is_clear() -> None:
    inv = _invoice("SE")
    res = evaluate_invoice_export_control(inv, lines=[_line(description="Office chairs", hs_code="9401")])
    assert res.flagged is False
    assert res.status == "clear"
    assert res.severity == "green"
    assert res.hits == []


def test_code_found_in_description_text() -> None:
    inv = _invoice("DE")
    res = evaluate_invoice_export_control(
        inv, lines=[_line(description="Spare part, ECCN 3A001 classified")]
    )
    assert res.flagged is True
    assert any(h.item_code == "3A001" for h in res.hits)
