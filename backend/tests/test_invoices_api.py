"""Ende-til-ende-tester for invoice-API-et."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient

from app.models.entity import Entity, EntityRole, EntityType
from app.models.invoice import ComplianceScore, Invoice, InvoiceDirection, InvoiceStatus


@pytest.mark.asyncio
async def test_upload_invoice_returns_invoice(
    client: AsyncClient, sample_pdf_bytes: bytes
) -> None:
    """Upload returnerer umiddelbart med status 'uploaded' — parsing skjer asynkront."""
    response = await client.post(
        "/api/v1/invoices/upload",
        files={"file": ("invoice.pdf", sample_pdf_bytes, "application/pdf")},
        data={"direction": "incoming"},
    )
    assert response.status_code == 201, response.text
    body = response.json()

    # Svaret er en InvoiceUploadResponse: {"invoice": {...}}
    assert "invoice" in body, f"Mangler 'invoice'-nøkkel i svaret: {list(body.keys())}"
    invoice = body["invoice"]

    # Parsing skjer i bakgrunnen — status er "uploaded" eller muligens "parsing"
    # like etter opplasting, aldri "parsed" synkront.
    assert invoice["status"] in {"uploaded", "parsing"}, f"Uventet status: {invoice['status']}"
    assert invoice["direction"] == "incoming"
    assert invoice["original_filename"] == "invoice.pdf"
    assert invoice["id"] is not None


@pytest.mark.asyncio
async def test_get_invoice_returns_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.get("/api/v1/invoices/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_list_invoices_returns_paginated_results(
    client: AsyncClient, sample_pdf_bytes: bytes
) -> None:
    for idx in range(3):
        unique_pdf = sample_pdf_bytes + f"\n%upload-{idx}".encode("utf-8")
        await client.post(
            "/api/v1/invoices/upload",
            files={"file": ("invoice.pdf", unique_pdf, "application/pdf")},
            data={"direction": "incoming"},
        )

    response = await client.get("/api/v1/invoices?limit=2&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/invoices/upload",
        files={"file": ("invoice.txt", b"not a pdf", "text/plain")},
        data={"direction": "incoming"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "UNSUPPORTED_FILE_TYPE"


@pytest.mark.asyncio
async def test_vat_mismatches_endpoint_returns_flagged_items(
    client: AsyncClient,
    db_session,
) -> None:
    flagged = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.OUTGOING,
        pdf_path="tests/fixtures/invoice_flagged.pdf",
        status=InvoiceStatus.EXTRACTED,
        vat_amount=Decimal("500.00"),
        vat_rate="25%",
        destination_country="DE",
    )
    ok = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.OUTGOING,
        pdf_path="tests/fixtures/invoice_ok.pdf",
        status=InvoiceStatus.EXTRACTED,
        vat_amount=Decimal("0.00"),
        vat_rate="0%",
        destination_country="DE",
    )
    db_session.add_all([flagged, ok])
    await db_session.flush()

    db_session.add_all(
        [
            Entity(
                id=uuid.uuid4(),
                invoice_id=flagged.id,
                name="Norsk Selger AS",
                entity_type=EntityType.COMPANY,
                country="NO",
                role=EntityRole.SELLER,
            ),
            Entity(
                id=uuid.uuid4(),
                invoice_id=flagged.id,
                name="German Buyer GmbH",
                entity_type=EntityType.COMPANY,
                country="DE",
                role=EntityRole.BUYER,
            ),
            Entity(
                id=uuid.uuid4(),
                invoice_id=ok.id,
                name="Norsk Selger AS",
                entity_type=EntityType.COMPANY,
                country="NO",
                role=EntityRole.SELLER,
            ),
            Entity(
                id=uuid.uuid4(),
                invoice_id=ok.id,
                name="German Buyer GmbH",
                entity_type=EntityType.COMPANY,
                country="DE",
                role=EntityRole.BUYER,
            ),
        ]
    )
    await db_session.commit()

    response = await client.get("/api/v1/invoices/vat-mismatches")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_scanned"] == 2
    assert body["total_flagged"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["invoice_id"] == str(flagged.id)
    assert body["items"][0]["vat_check"]["flagged"] is True


@pytest.mark.asyncio
async def test_review_allows_controller_above_old_limit(client: AsyncClient, db_session) -> None:
    inv = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/review_limit.pdf",
        status=InvoiceStatus.SCREENED,
        total_amount=Decimal("1500.00"),
        currency="EUR",
    )
    db_session.add(inv)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/invoices/{inv.id}/review",
        json={
            "decision": "approved",
            "reason": "Controller godkjenner etter compliance-vurdering.",
            "rule_reference": "POL-APPROVAL-001",
            "evidence_summary": "Beløpsgrense håndteres i økonomisystemet, ikke her.",
            "deviation_approval": True,
        },
        headers={"X-Actor-Role": "controller", "X-Actor-Name": "Kari Controller"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_review_allows_c_level_above_compliance_limit(client: AsyncClient, db_session) -> None:
    inv = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/review_c_level.pdf",
        status=InvoiceStatus.SCREENED,
        total_amount=Decimal("7000.00"),
        currency="USD",
    )
    db_session.add(inv)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/invoices/{inv.id}/review",
        json={
            "decision": "approved",
            "reason": "Sjef godkjenner høyere beløp etter vurdering.",
            "rule_reference": "POL-APPROVAL-001",
            "evidence_summary": "C-level kan godkjenne over compliance-grense.",
            "deviation_approval": True,
        },
        headers={"X-Actor-Role": "c_level", "X-Actor-Name": "Sigurd Sjef"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_upload_duplicate_reuses_existing_invoice(
    client: AsyncClient, sample_pdf_bytes: bytes
) -> None:
    first = await client.post(
        "/api/v1/invoices/upload",
        files={"file": ("dup.pdf", sample_pdf_bytes, "application/pdf")},
        data={"direction": "incoming"},
    )
    assert first.status_code == 201, first.text
    first_body = first.json()
    first_id = first_body["invoice"]["id"]

    second = await client.post(
        "/api/v1/invoices/upload",
        files={"file": ("dup.pdf", sample_pdf_bytes, "application/pdf")},
        data={"direction": "incoming"},
    )
    assert second.status_code == 201, second.text
    second_body = second.json()
    assert second_body["duplicate_detected"] is True
    assert second_body["duplicate_of_invoice_id"] == first_id
    assert second_body["invoice"]["id"] == first_id


@pytest.mark.asyncio
async def test_review_and_next_returns_next_invoice_and_claims_it(client: AsyncClient, db_session) -> None:
    first = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/review_next_1.pdf",
        status=InvoiceStatus.SCREENED,
        compliance_score=ComplianceScore.RED,
    )
    second = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/review_next_2.pdf",
        status=InvoiceStatus.SCREENED,
        compliance_score=ComplianceScore.YELLOW,
    )
    db_session.add_all([first, second])
    await db_session.commit()

    response = await client.post(
        f"/api/v1/invoices/{first.id}/review-and-next",
        json={
            "decision": "approved",
            "reason": "Manuell kontroll utført av compliance.",
            "rule_reference": "POL-REV-001",
            "evidence_summary": "Sanksjonsfunn vurdert og dokumentert.",
            "deviation_approval": True,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["invoice"]["status"] == "approved"
    assert body["next_invoice_id"] == str(second.id)

    claimed_next = await client.get(f"/api/v1/invoices/{second.id}")
    assert claimed_next.status_code == 200
    assert claimed_next.json()["review_claimed_by"] == "pytest-admin"


@pytest.mark.asyncio
async def test_claim_endpoint_returns_409_when_claimed_by_other(client: AsyncClient, db_session) -> None:
    inv = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/claim_conflict.pdf",
        status=InvoiceStatus.SCREENED,
        compliance_score=ComplianceScore.RED,
        review_claimed_by="Another Reviewer",
        review_claimed_at=datetime.now(UTC),
    )
    db_session.add(inv)
    await db_session.commit()

    response = await client.post(f"/api/v1/invoices/{inv.id}/claim")
    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_invoice_list_preferences_roundtrip(client: AsyncClient) -> None:
    initial = await client.get("/api/v1/invoices/preferences/invoice-list")
    assert initial.status_code == 200, initial.text
    assert initial.json()["table_col_widths"] == {}

    payload = {
        "table_col_widths": {"file": 260, "llm": 420},
        "table_col_presets": [
            {"id": "custom_1", "label": "Custom 1", "widths": {"file": 260, "llm": 420}},
        ],
        "default_filters": {"sort_by": "created_at", "sort_dir": "desc"},
    }
    updated = await client.put("/api/v1/invoices/preferences/invoice-list", json=payload)
    assert updated.status_code == 200, updated.text
    updated_body = updated.json()
    assert updated_body["table_col_widths"]["file"] == 260
    assert updated_body["table_col_presets"][0]["id"] == "custom_1"

    fetched = await client.get("/api/v1/invoices/preferences/invoice-list")
    assert fetched.status_code == 200, fetched.text
    fetched_body = fetched.json()
    assert fetched_body["table_col_widths"]["llm"] == 420
    assert fetched_body["default_filters"]["sort_dir"] == "desc"
