#!/usr/bin/env python
"""
Generer initielle fasit-YAML-filer for alle faktura-filer i Test_invoices/.

Skriptet kjører den komplette parse → heuristikk → LLM-ekstraksjon-pipelinen
for hver faktura og skriver resultatet til
  tests/fixtures/expected/<filnavn-uten-ext>.yaml

Eksisterende YAML-filer overskrives IKKE hvis de allerede inneholder
verifiserte verdier (felter ≠ null). Bruk --overwrite for å tvinge.

Bruk:
  cd backend/
  python scripts/generate_ground_truth.py
  python scripts/generate_ground_truth.py --overwrite
  python scripts/generate_ground_truth.py --dir /sti/til/faktura-katalog

Krav:
  • Miljøvariabelen DATABASE_URL trenger IKKE å være satt — skriptet
    kaller LLM-et direkte og lagrer ikke til DB.
  • LLM-API-nøkkel (ANTHROPIC_API_KEY eller OPENAI_API_KEY) må finnes
    i .secrets eller miljøet.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Legg til backend/ i Python-sti slik at «app» kan importeres direkte.
_BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

# Sett dummy-verdier for påkrevde Settings-felt så Settings ikke krasjer
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://dummy:dummy@localhost/dummy")
os.environ.setdefault("APP_SECRET_KEY", "dummy-secret-for-script")
os.environ.setdefault("APP_ENV", "development")

_PROJECT_ROOT = _BACKEND_DIR.parent
_EXPECTED_DIR = _BACKEND_DIR / "tests" / "fixtures" / "expected"
_SUPPORTED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx"}


# ── Kjerne-logikk ─────────────────────────────────────────────────────────────


def _discover_invoices(directory: Path) -> list[Path]:
    return sorted(
        p for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in _SUPPORTED_EXT
    )


def _existing_has_values(yaml_path: Path) -> bool:
    """Returner True hvis YAML-filen inneholder minst ett ikke-null felt."""
    if not yaml_path.exists():
        return False
    import yaml
    with yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    scalar_fields = [
        "invoice_number", "invoice_date", "total_amount", "currency",
        "incoterms", "transport_mode", "destination_country", "po_number",
    ]
    return any(data.get(f) is not None for f in scalar_fields)


async def _extract_invoice(invoice_path: Path) -> dict:
    """Kjør parse → heuristikk → LLM og returner et YAML-vennlig resultat-dict."""
    from app.core.config import get_settings
    from app.llm.factory import get_llm_client
    from app.llm.heuristics import HeuristicExtractor
    from app.llm.merger import merge
    from app.parsers import parse_pdf
    from app.parsers.models import SourceFileType

    settings = get_settings()

    # Parsing
    print(f"  Parsing {invoice_path.name} ...", flush=True)
    parsed = parse_pdf(invoice_path)
    print(f"    -> {parsed.method.value}, {parsed.page_count} side(r), {len(parsed.text)} tegn")

    # Heuristikk
    extractor = HeuristicExtractor()
    heuristic = extractor.extract(parsed.text)

    # LLM
    print("  LLM-ekstraksjon ...", flush=True)
    active_model = settings.llm_primary_model
    client = get_llm_client(active_model)
    file_type = SourceFileType.from_filename(invoice_path.name)
    image_path = invoice_path if file_type == SourceFileType.IMAGE else None

    result = await client.extract_invoice(
        parsed.text,
        image_path=image_path,
        confidence_threshold=settings.confidence_threshold,
    )

    # Merge
    result = merge(
        result, heuristic,
        raw_text=parsed.text,
        threshold=settings.confidence_threshold,
        filename=invoice_path.name,
    )
    result.compute_derived(threshold=settings.confidence_threshold)

    print(
        f"    → model={result.model_id}"
        f"  confidence={result.overall_confidence:.2f}"
        f"  linjer={len(result.lines)}"
        f"  entiteter={len(result.entities)}"
    )

    # Bygg YAML-dict
    def _fv(field_value) -> str | None:  # FieldValue → str | None
        return field_value.value if field_value.value else None

    entities_list = [
        {k: v for k, v in {
            "name": e.name or None,
            "role": e.role or None,
            "entity_type": e.entity_type or None,
            "country": e.country or None,
            "address": e.address or None,
        }.items() if v is not None}
        for e in result.entities
    ]

    lines_list = [
        {k: v for k, v in {
            "description": line.description or None,
            "hs_code": line.hs_code or None,
            "eccn": line.eccn or None,
            "country_of_origin": line.country_of_origin or None,
            "currency": line.currency or None,
            "quantity": line.quantity or None,
            "unit_price": line.unit_price or None,
            "total_price": line.total_price or None,
        }.items() if v is not None}
        for line in result.lines
    ]

    return {
        "invoice_number": _fv(result.invoice_number),
        "invoice_date": _fv(result.invoice_date),
        "total_amount": _fv(result.total_amount),
        "currency": _fv(result.currency),
        "incoterms": _fv(result.incoterms),
        "transport_mode": _fv(result.transport_mode),
        "destination_country": _fv(result.destination_country),
        "po_number": _fv(result.po_number),
        "entities": entities_list,
        "lines": lines_list,
        "_meta": {
            "model": result.model_id,
            "overall_confidence": round(result.overall_confidence, 3),
            "low_confidence_fields": result.low_confidence_fields,
            "source_file": invoice_path.name,
            "parse_method": parsed.method.value,
            "text_length": len(parsed.text),
            "status": "AUTO_GENERATED — IKKE VERIFISERT",
        },
    }


def _write_yaml(yaml_path: Path, data: dict) -> None:
    import yaml

    _EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    header = (
        f"# Fasit for {data['_meta']['source_file']}\n"
        f"# Generert automatisk — IKKE VERIFISERT\n"
        f"# Modell: {data['_meta']['model']}  "
        f"Konfidens: {data['_meta']['overall_confidence']}\n"
        f"# Lav-konfidens-felt: {', '.join(data['_meta']['low_confidence_fields']) or 'ingen'}\n"
        f"#\n"
        f"# Korriger verdiene manuelt mot originaldokumentet og fjern denne advarselen.\n"
        f"# Sett felt du ikke vil sammenligne til null.\n\n"
    )

    # Fjern _meta fra YAML-innholdet
    yaml_data = {k: v for k, v in data.items() if k != "_meta"}

    with yaml_path.open("w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.dump(
            yaml_data,
            fh,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
        )


async def _main(invoice_dir: Path, overwrite: bool) -> None:
    invoices = _discover_invoices(invoice_dir)
    if not invoices:
        print(f"Ingen faktura-filer funnet i {invoice_dir}")
        return

    print(f"Fant {len(invoices)} faktura-fil(er) i {invoice_dir}\n")
    _EXPECTED_DIR.mkdir(parents=True, exist_ok=True)

    for invoice_path in invoices:
        yaml_path = _EXPECTED_DIR / f"{invoice_path.stem}.yaml"
        print(f"[{invoice_path.name}]")

        if not overwrite and _existing_has_values(yaml_path):
            print("  Fasit finnes allerede — hopper over (bruk --overwrite for å overskrive)\n")
            continue

        try:
            data = await _extract_invoice(invoice_path)
        except Exception as exc:
            print(f"  FEIL: {exc}\n")
            continue

        _write_yaml(yaml_path, data)
        print(f"  Skrevet til {yaml_path.relative_to(_BACKEND_DIR)}\n")

    print("Ferdig. Korriger YAML-filene manuelt mot originaldokumentene.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir",
        default=str(_PROJECT_ROOT / "Test_invoices"),
        help="Sti til faktura-katalog (default: <prosjektrot>/Test_invoices)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overskriv eksisterende fasit-filer selv om de inneholder verifiserte verdier",
    )
    args = parser.parse_args()

    invoice_dir = Path(args.dir)
    if not invoice_dir.exists():
        print(f"Feil: katalogen {invoice_dir} finnes ikke")
        sys.exit(1)

    asyncio.run(_main(invoice_dir, args.overwrite))


if __name__ == "__main__":
    main()
