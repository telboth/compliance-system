from __future__ import annotations

import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "Test_invoices" / "ground_truth_manifest.csv"
INVOICES_DIR = PROJECT_ROOT / "Test_invoices"


def _load_rows() -> list[dict[str, str]]:
    with MANIFEST_PATH.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_manifest_exists() -> None:
    assert MANIFEST_PATH.exists(), f"Mangler manifest: {MANIFEST_PATH}"


def test_manifest_rows_reference_existing_files() -> None:
    rows = _load_rows()
    assert rows, "Manifest er tom."

    for row in rows:
        file_name = str(row.get("file") or "").strip()
        assert file_name, f"Tomt filnavn i rad: {row}"
        invoice_path = INVOICES_DIR / file_name
        assert invoice_path.exists(), f"Fil mangler: {invoice_path}"


def test_manifest_status_values_and_flagged_metadata() -> None:
    rows = _load_rows()
    assert rows, "Manifest er tom."
    allowed = {"CLEAN", "FLAGGED"}

    flagged_count = 0
    clean_count = 0

    for row in rows:
        expected_status = str(row.get("expected_status") or "").strip().upper()
        assert expected_status in allowed, (
            f"Ugyldig expected_status={expected_status!r} i rad: {row}"
        )

        sanctions_entity = str(row.get("sanctions_test_entity") or "").strip()
        test_location = str(row.get("test_location") or "").strip()
        if expected_status == "FLAGGED":
            flagged_count += 1
            assert sanctions_entity, (
                "FLAGGED-rad må ha sanctions_test_entity. Rad: "
                f"{row}"
            )
            assert test_location, (
                "FLAGGED-rad må ha test_location. Rad: "
                f"{row}"
            )
        else:
            clean_count += 1

    # Sikrer at matrisen faktisk dekker begge klasser.
    assert clean_count > 0, "Manifest mangler CLEAN-caser."
    assert flagged_count > 0, "Manifest mangler FLAGGED-caser."

