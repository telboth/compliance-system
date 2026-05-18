"""Kjor regresjon mot Test_invoices/ground_truth_manifest.csv via API."""

from __future__ import annotations

import argparse
import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

TERMINAL_STATUSES = {
    "screened",
    "screening_failed",
    "extraction_failed",
    "parsing_failed",
}


@dataclass(frozen=True)
class ManifestRow:
    invoice_no: str
    file_name: str
    expected_status: str
    sanctions_test_entity: str

    @property
    def expected_flagged(self) -> bool:
        return self.expected_status.strip().upper() == "FLAGGED"


def _load_manifest(path: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(
                ManifestRow(
                    invoice_no=str(row.get("invoice_no") or "").strip(),
                    file_name=str(row.get("file") or "").strip(),
                    expected_status=str(row.get("expected_status") or "").strip(),
                    sanctions_test_entity=str(row.get("sanctions_test_entity") or "").strip(),
                )
            )
    return rows


def _find_existing_invoice_id(
    client: httpx.Client,
    api_base: str,
    file_name: str,
) -> str | None:
    offset = 0
    limit = 200
    while offset <= 2000:
        response = client.get(
            f"{api_base}/invoices",
            params={"limit": limit, "offset": offset, "sort_by": "created_at", "sort_dir": "desc"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items") or []
        if not items:
            return None
        for item in items:
            if str(item.get("original_filename") or "").strip() == file_name:
                return str(item.get("id"))
        offset += limit
    return None


def _upload_invoice(
    client: httpx.Client,
    api_base: str,
    invoice_path: Path,
) -> str:
    with invoice_path.open("rb") as fh:
        response = client.post(
            f"{api_base}/invoices/upload",
            data={"direction": "incoming"},
            files={"file": (invoice_path.name, fh, "application/pdf")},
            timeout=120,
        )
    response.raise_for_status()
    payload = response.json()
    invoice = payload.get("invoice") or {}
    invoice_id = str(invoice.get("id") or "")
    if not invoice_id:
        raise RuntimeError(f"Mangler invoice-id i upload-respons for {invoice_path.name}")
    return invoice_id


def _wait_for_terminal_status(
    client: httpx.Client,
    api_base: str,
    invoice_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] = {}
    while time.time() < deadline:
        response = client.get(f"{api_base}/invoices/{invoice_id}", timeout=30)
        response.raise_for_status()
        payload = response.json()
        last_payload = payload
        status = str(payload.get("status") or "")
        if status in TERMINAL_STATUSES:
            return payload
        time.sleep(2.5)
    raise TimeoutError(
        f"Timeout venter på terminal status for invoice {invoice_id} "
        f"(siste={last_payload.get('status')!r})"
    )


def _screening_summary(
    client: httpx.Client,
    api_base: str,
    invoice_id: str,
) -> tuple[int, int]:
    response = client.get(f"{api_base}/invoices/{invoice_id}/screening", timeout=30)
    if response.status_code >= 400:
        return (0, 0)
    payload = response.json()
    confirmed = int(payload.get("confirmed_matches") or 0)
    potential = int(payload.get("potential_matches") or 0)
    return (confirmed, potential)


def _predicted_flag(invoice_payload: dict[str, Any], confirmed: int, potential: int) -> bool:
    score = str(invoice_payload.get("compliance_score") or "").lower()
    if score in {"yellow", "red"}:
        return True
    return (confirmed + potential) > 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000/api/v1",
        help="API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--manifest",
        default=str(Path(__file__).resolve().parents[2] / "Test_invoices" / "ground_truth_manifest.csv"),
        help="Sti til ground_truth_manifest.csv",
    )
    parser.add_argument(
        "--invoices-dir",
        default=str(Path(__file__).resolve().parents[2] / "Test_invoices"),
        help="Katalog med testfiler",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=600,
        help="Maks ventetid per invoice",
    )
    parser.add_argument(
        "--force-upload",
        action="store_true",
        help="Last alltid opp pa nytt i stedet for å gjenbruke siste invoice med samme filnavn.",
    )
    parser.add_argument(
        "--actor-role",
        default="admin",
        help="Rolle-header for backend auth (X-Actor-Role).",
    )
    parser.add_argument(
        "--actor-name",
        default="ground-truth-regression",
        help="Navn-header for backend auth (X-Actor-Name).",
    )
    parser.add_argument(
        "--min-precision",
        type=float,
        default=0.0,
        help="Fail hvis precision havner under denne terskelen.",
    )
    parser.add_argument(
        "--min-recall",
        type=float,
        default=0.0,
        help="Fail hvis recall havner under denne terskelen.",
    )
    parser.add_argument(
        "--min-accuracy",
        type=float,
        default=0.0,
        help="Fail hvis accuracy havner under denne terskelen.",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    invoices_dir = Path(args.invoices_dir)
    rows = _load_manifest(manifest_path)
    if not rows:
        raise RuntimeError(f"Ingen rader i manifest: {manifest_path}")

    tp = tn = fp = fn = 0
    completed = 0
    print(f"Starter regresjon: {len(rows)} invoices")
    with httpx.Client(
        timeout=60,
        headers={
            "X-Actor-Role": str(args.actor_role),
            "X-Actor-Name": str(args.actor_name),
        },
    ) as client:
        for row in rows:
            invoice_path = invoices_dir / row.file_name
            if not invoice_path.exists():
                print(f"[MISSING] {row.file_name} finnes ikke i {invoices_dir}")
                continue

            invoice_id: str | None = None
            if not args.force_upload:
                invoice_id = _find_existing_invoice_id(client, args.api_base, row.file_name)

            if invoice_id is None:
                invoice_id = _upload_invoice(client, args.api_base, invoice_path)
                action = "upload"
            else:
                action = "reuse"

            payload = _wait_for_terminal_status(
                client,
                args.api_base,
                invoice_id,
                timeout_seconds=max(60, int(args.timeout_seconds)),
            )
            confirmed, potential = _screening_summary(client, args.api_base, invoice_id)
            predicted = _predicted_flag(payload, confirmed, potential)
            expected = row.expected_flagged

            if expected and predicted:
                tp += 1
                verdict = "TP"
            elif (not expected) and (not predicted):
                tn += 1
                verdict = "TN"
            elif (not expected) and predicted:
                fp += 1
                verdict = "FP"
            else:
                fn += 1
                verdict = "FN"

            completed += 1
            print(
                f"[{verdict}] {row.file_name} ({action}) status={payload.get('status')} "
                f"score={payload.get('compliance_score')} confirmed={confirmed} "
                f"potential={potential} expected={'FLAGGED' if expected else 'CLEAN'}"
            )

    precision = (tp / (tp + fp)) if (tp + fp) else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) else 0.0
    accuracy = ((tp + tn) / completed) if completed else 0.0
    print("\n--- Oppsummering ---")
    print(f"Kjørte: {completed}/{len(rows)}")
    print(f"TP={tp} FP={fp} TN={tn} FN={fn}")
    print(f"Precision={precision:.3f} Recall={recall:.3f} Accuracy={accuracy:.3f}")
    if completed == 0:
        return 1
    if precision < args.min_precision:
        print(f"FAIL: precision {precision:.3f} < terskel {args.min_precision:.3f}")
        return 1
    if recall < args.min_recall:
        print(f"FAIL: recall {recall:.3f} < terskel {args.min_recall:.3f}")
        return 1
    if accuracy < args.min_accuracy:
        print(f"FAIL: accuracy {accuracy:.3f} < terskel {args.min_accuracy:.3f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
