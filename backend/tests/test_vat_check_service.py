"""Tester for VAT-heurstikk."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.entity import Entity, EntityRole, EntityType
from app.models.invoice import Invoice, InvoiceDirection, InvoiceStatus
from app.services.vat_check_service import evaluate_invoice_vat_mismatch


@pytest.mark.asyncio
async def test_vat_mismatch_flags_export_with_vat(db_session) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.OUTGOING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
        vat_amount=Decimal("1250.00"),
        vat_rate="25%",
        destination_country="DE",
    )
    db_session.add(invoice)
    await db_session.flush()
    db_session.add_all(
        [
            Entity(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                name="Norsk Selger AS",
                entity_type=EntityType.COMPANY,
                country="NO",
                role=EntityRole.SELLER,
            ),
            Entity(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                name="German Buyer GmbH",
                entity_type=EntityType.COMPANY,
                country="DE",
                role=EntityRole.BUYER,
            ),
        ]
    )
    await db_session.commit()
    loaded = (
        await db_session.execute(
            select(Invoice).where(Invoice.id == invoice.id).options(selectinload(Invoice.entities))
        )
    ).scalar_one()

    check = evaluate_invoice_vat_mismatch(loaded)
    assert check.export_detected is True
    assert check.has_vat is True
    assert check.flagged is True


@pytest.mark.asyncio
async def test_vat_mismatch_not_flagged_when_zero_vat(db_session) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.OUTGOING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
        vat_amount=Decimal("0.00"),
        vat_rate="0%",
        destination_country="DE",
    )
    db_session.add(invoice)
    await db_session.flush()
    db_session.add_all(
        [
            Entity(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                name="Norsk Selger AS",
                entity_type=EntityType.COMPANY,
                country="NO",
                role=EntityRole.SELLER,
            ),
            Entity(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                name="German Buyer GmbH",
                entity_type=EntityType.COMPANY,
                country="DE",
                role=EntityRole.BUYER,
            ),
        ]
    )
    await db_session.commit()
    loaded = (
        await db_session.execute(
            select(Invoice).where(Invoice.id == invoice.id).options(selectinload(Invoice.entities))
        )
    ).scalar_one()

    check = evaluate_invoice_vat_mismatch(loaded)
    assert check.export_detected is True
    assert check.has_vat is False
    assert check.flagged is False
