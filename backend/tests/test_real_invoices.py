"""
Integrasjonstester mot ekte faktura-filer i Test_invoices/.

Testene er delt i to grupper:

  1. ``test_parsing`` (pytest.mark.slow)
     Kaller parse_pdf() på alle filer og verifiserer at tekst ekstraheres.
     Ingen DB-tilgang, ingen LLM-kall. Egnet for rask røyksjekk av OCR-pipelinen.

  2. ``test_extraction_pipeline`` (pytest.mark.slow + pytest.mark.integration)
     Full pipeline: parse → LLM-ekstraksjon → DB-lagring.
     Sammenligner mot fasit-YAML hvis den finnes og printer en
     precision/recall-rapport per felt til slutt.

Kjøring
-------
  # Bare parsing (ingen LLM-API-kall):
  pytest tests/test_real_invoices.py -k test_parsing -m slow -v -s

  # Full pipeline:
  pytest tests/test_real_invoices.py -k test_extraction_pipeline -m slow -v -s

  # Alt:
  pytest tests/test_real_invoices.py -m slow -v -s

Miljøvariabler
--------------
  TEST_INVOICES_DIR  Sti til faktura-katalog (default: <prosjektrot>/Test_invoices)

Fasitfiler
----------
  tests/fixtures/expected/<filnavn-uten-ext>.yaml

  Felt med verdi ``null`` hoppes over.
  Generer initielle verdier med: ``python scripts/generate_ground_truth.py``
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

# ── Stier ─────────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent.parent  # compliance-system/
_EXPECTED_DIR = Path(__file__).parent / "fixtures" / "expected"
_TEST_INVOICES_DIR = Path(os.environ.get("TEST_INVOICES_DIR", str(_PROJECT_ROOT / "Test_invoices")))
_SUPPORTED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx"}

# ── Oppdagelse av testfiler ───────────────────────────────────────────────────


def _discover_invoices() -> list[Path]:
    """Finn alle støttede faktura-filer i TEST_INVOICES_DIR rekursivt."""
    if not _TEST_INVOICES_DIR.exists():
        return []
    return sorted(p for p in _TEST_INVOICES_DIR.rglob("*") if p.is_file() and p.suffix.lower() in _SUPPORTED_EXT)


_ALL_INVOICES = _discover_invoices()

if not _ALL_INVOICES:
    pytest.skip(
        f"Ingen faktura-filer i {_TEST_INVOICES_DIR} — legg til filer eller sett TEST_INVOICES_DIR",
        allow_module_level=True,
    )

_INVOICE_IDS = [p.name for p in _ALL_INVOICES]

# ── Fasit-hjelp ───────────────────────────────────────────────────────────────


def _load_ground_truth(invoice_path: Path) -> dict[str, Any]:
    """Last fasit-YAML for en faktura. Returnerer {} hvis ingen fasit finnes."""
    yaml_path = _EXPECTED_DIR / f"{invoice_path.stem}.yaml"
    if not yaml_path.exists():
        return {}
    with yaml_path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _amounts_match(expected: str, actual: str | None, tol: float = 0.01) -> bool:
    if actual is None:
        return False
    try:
        return abs(float(expected) - float(str(actual))) <= tol
    except ValueError:
        return expected.strip() == str(actual).strip()


def _field_matches(field: str, expected: Any, actual: Any) -> bool:
    """Returner True hvis feltet matcher fasit, eller fasit er null (hopp over)."""
    if expected is None:
        return True
    actual_str = str(actual).strip() if actual is not None else None
    expected_str = str(expected).strip()
    if field == "total_amount":
        return _amounts_match(expected_str, actual_str)
    if actual_str is None:
        return False
    return expected_str.upper() == actual_str.upper()


# ── Akkumulering for nøyaktighetsrapport ──────────────────────────────────────

# Modul-global — fylles opp av test_extraction_pipeline, leses av _accuracy_report
_field_results: dict[str, list[bool]] = {}


def _record(field: str, expected: Any, actual: Any) -> None:
    """Registrer ett felt-utfall i nøyaktighets-akkumulatoren."""
    if expected is None:
        return
    _field_results.setdefault(field, []).append(_field_matches(field, expected, actual))


@pytest.fixture(scope="module", autouse=True)
def _accuracy_report() -> Any:
    """Printer en nøyaktighetsrapport (recall per felt) etter alle modul-tester."""
    _field_results.clear()
    yield
    if not _field_results:
        return

    lines = [
        "",
        "=" * 62,
        "  EKSTRASJONS-NØYAKTIGHET (recall per felt)",
        "=" * 62,
    ]
    for field, matches in sorted(_field_results.items()):
        n = len(matches)
        ok = sum(matches)
        pct = 100 * ok / n if n else 0
        bar_filled = int(pct / 5)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)
        lines.append(f"  {field:<30s} {bar} {ok}/{n} ({pct:.0f}%)")
    lines.append("=" * 62)
    print("\n".join(lines))


# ── 1. Parsing-røyktester (synkron, ingen DB/LLM) ────────────────────────────


@pytest.mark.slow
@pytest.mark.parametrize("invoice_path", _ALL_INVOICES, ids=_INVOICE_IDS)
def test_parsing(invoice_path: Path) -> None:
    """Verifiser at parseren klarer å lese alle faktura-filer i Test_invoices/.

    Kaller parse_pdf() og sjekker at vi får ut meningsfull tekst.
    Ingen DB-tilgang og ingen LLM-kall — egnet som rask OCR-røyksjekk.
    """
    from app.parsers import parse_pdf

    result = parse_pdf(invoice_path)

    assert result is not None, f"parse_pdf returnerte None for {invoice_path.name}"
    assert result.page_count >= 1, f"Ingen sider registrert for {invoice_path.name}"
    assert len(result.text) >= 30, f"For lite tekst ekstrahert fra {invoice_path.name}: {len(result.text)} tegn"

    print(
        f"\n  [{invoice_path.name}]  metode={result.method.value}  sider={result.page_count}  tegn={len(result.text)}"
    )


# ── 2. Full pipeline-tester (parse → LLM-ekstraksjon → DB) ───────────────────


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize("invoice_path", _ALL_INVOICES, ids=_INVOICE_IDS)
async def test_extraction_pipeline(
    invoice_path: Path,
    db_session: Any,  # pytest_asyncio-fixture fra conftest.py
) -> None:
    """Full pipeline: parse → LLM-ekstraksjon → DB → fasit-sammenligning.

    Hvert test-kall starter mot en frisk database (db_session-fixture i conftest
    dropper og oppretter alle tabeller på nytt per test). Fasit-filen
    tests/fixtures/expected/<filnavn>.yaml brukes til felt-sammenligning;
    felt med ``null`` hoppes over.
    """
    from app.models.invoice import Invoice, InvoiceDirection, InvoiceStatus
    from app.parsers import parse_pdf
    from app.services.extraction_service import run_extraction
    from app.services.invoice_service import get_invoice

    # ── 1. Parse faktura-filen ───────────────────────────────────────────────
    parsed = parse_pdf(invoice_path)
    assert parsed.text, f"Tom tekst etter parsing av {invoice_path.name}"

    print(f"\n  [{invoice_path.name}]  parsing: metode={parsed.method.value}  tegn={len(parsed.text)}")

    # ── 2. Lagre i test-DB (omgår file_storage — peker direkte på originalfil) ─
    invoice = Invoice(
        pdf_path=str(invoice_path),  # brukes for image-deteksjon i extraction
        original_filename=invoice_path.name,
        file_size_bytes=invoice_path.stat().st_size,
        direction=InvoiceDirection.INCOMING,
        status=InvoiceStatus.PARSED,
        raw_text=parsed.text,
    )
    db_session.add(invoice)
    await db_session.commit()
    await db_session.refresh(invoice)
    invoice_id = invoice.id

    # ── 3. LLM-ekstraksjon ───────────────────────────────────────────────────
    _invoice, result = await run_extraction(db_session, invoice_id, model_id=None)

    # Hent fersk kopi med innlastede relasjoner (lines/entities)
    invoice = await get_invoice(db_session, invoice_id)

    # ── 4. Grunnleggende røyksjekk ───────────────────────────────────────────
    assert invoice.status in {InvoiceStatus.EXTRACTED, InvoiceStatus.EXTRACTION_FAILED}, (
        f"Uventet status: {invoice.status}"
    )

    if invoice.status == InvoiceStatus.EXTRACTION_FAILED:
        pytest.fail(f"Ekstraksjon feilet for {invoice_path.name}: {invoice.extraction_error}")

    conf = invoice.extraction_confidence or {}
    print(
        f"  ekstraksjon:"
        f"  model={invoice.extraction_model}"
        f"  confidence={conf.get('overall', 0):.2f}"
        f"  linjer={len(invoice.lines)}"
        f"  entiteter={len(invoice.entities)}"
    )

    # ── 5. Fasit-sammenligning ────────────────────────────────────────────────
    gt = _load_ground_truth(invoice_path)
    if not gt:
        print("  Ingen fasit — hopper over felt-sammenligning")
        return

    mismatches: list[str] = []

    # Skalar-felt
    scalar_fields = [
        "invoice_number",
        "invoice_date",
        "total_amount",
        "currency",
        "incoterms",
        "transport_mode",
        "destination_country",
        "po_number",
    ]
    for field in scalar_fields:
        expected = gt.get(field)
        actual = getattr(invoice, field, None)
        _record(field, expected, actual)
        if expected is not None and not _field_matches(field, expected, actual):
            mismatches.append(f"{field}: forventet={expected!r}  faktisk={actual!r}")

    # Entitets-sjekk — finn minst én match per forventet entitet
    for exp_ent in gt.get("entities") or []:
        exp_name: str | None = exp_ent.get("name")
        exp_role: str | None = exp_ent.get("role")
        if exp_name is None and exp_role is None:
            continue
        found = any(
            (exp_role is None or e.role.value == exp_role)
            and (exp_name is None or exp_name.lower() in (e.name or "").lower())
            for e in invoice.entities
        )
        label = f"{exp_role}:{exp_name}"
        _record("entities", label, label if found else None)
        if not found:
            mismatches.append(f"entitet ikke funnet: {exp_role}/{exp_name}")

    # Linje-felt-sjekk (i rekkefølge, felt for felt)
    for i, exp_line in enumerate(gt.get("lines") or []):
        if i >= len(invoice.lines):
            mismatches.append(f"linje {i + 1} mangler i ekstraksjon")
            continue
        actual_line = invoice.lines[i]
        for lf in ["hs_code", "eccn", "country_of_origin", "currency"]:
            ev = exp_line.get(lf)
            av = getattr(actual_line, lf, None)
            _record(f"line.{lf}", ev, av)
            if ev is not None and not _field_matches(lf, ev, av):
                mismatches.append(f"linje {i + 1} {lf}: forventet={ev!r}  faktisk={av!r}")

    # ── 6. Rapporter avvik ───────────────────────────────────────────────────
    if mismatches:
        print(f"  AVVIK ({len(mismatches)}):")
        for m in mismatches:
            print(f"    ✗ {m}")
    else:
        print("  Alle fasit-felt stemmer ✓")

    # Vi feiler IKKE på avvik — rapporten er informativ, ikke blokkerende.
    # Endre dette til ``assert not mismatches`` hvis du vil blokkere CI.
