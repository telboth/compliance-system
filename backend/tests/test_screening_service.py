"""Tester for screening_service."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models.entity import Entity, EntityRole, EntityType
from app.models.invoice import ComplianceScore, Invoice, InvoiceDirection, InvoiceStatus
from app.models.screening import MatchStatus, ScreeningResult
from app.sanctions.yente_client import YenteMatch
from app.services.screening_service import _normalize_candidate_name, screen_invoice


@pytest.mark.asyncio
async def test_screening_uses_latest_run_wins(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
        destination_country="DE",
    )
    db_session.add(invoice)
    await db_session.flush()

    entity = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="Acme Corp",
        entity_type=EntityType.COMPANY,
        country="DE",
        role=EntityRole.BUYER,
    )
    db_session.add(entity)
    await db_session.commit()

    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def match_entities_batch(self, entities, max_concurrent=5):
            e = entities[0]
            return {
                str(e["id"]): [
                    YenteMatch(
                        dataset="eu_fsf",
                        entity_id="eu-1",
                        matched_name="ACME CORP",
                        score=0.83,
                        listed_on=date(2026, 1, 1),
                        raw={"source": "test"},
                    )
                ]
            }

    monkeypatch.setattr("app.services.screening_service.get_yente_client", lambda: FakeYente())

    await screen_invoice(db_session, invoice.id)
    first_count = (
        await db_session.execute(
            select(func.count())
            .select_from(ScreeningResult)
            .where(ScreeningResult.invoice_id == invoice.id)
        )
    ).scalar_one()
    assert first_count == 1

    # Kjør på nytt: gamle resultater skal slettes, ikke akkumuleres.
    await screen_invoice(db_session, invoice.id)
    second_count = (
        await db_session.execute(
            select(func.count())
            .select_from(ScreeningResult)
            .where(ScreeningResult.invoice_id == invoice.id)
        )
    ).scalar_one()
    assert second_count == 1

    saved = (
        await db_session.execute(
            select(ScreeningResult).where(ScreeningResult.invoice_id == invoice.id)
        )
    ).scalar_one()
    assert saved.status == MatchStatus.POTENTIAL_MATCH
    assert saved.score == Decimal("0.8300")


@pytest.mark.asyncio
async def test_screening_accepts_screening_status(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.SCREENING,
        destination_country="DE",
    )
    db_session.add(invoice)
    await db_session.flush()

    entity = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="Acme Corp",
        entity_type=EntityType.COMPANY,
        country="DE",
        role=EntityRole.BUYER,
    )
    db_session.add(entity)
    await db_session.commit()

    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def match_entities_batch(self, entities, max_concurrent=5):
            e = entities[0]
            return {
                str(e["id"]): [
                    YenteMatch(
                        dataset="eu_fsf",
                        entity_id="eu-1",
                        matched_name="ACME CORP",
                        score=0.83,
                        listed_on=date(2026, 1, 1),
                        raw={"source": "test"},
                    )
                ]
            }

    monkeypatch.setattr("app.services.screening_service.get_yente_client", lambda: FakeYente())

    updated = await screen_invoice(db_session, invoice.id)
    assert updated.status == InvoiceStatus.SCREENED


@pytest.mark.asyncio
async def test_screening_sets_failed_status_on_exception(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
        destination_country="DE",
    )
    db_session.add(invoice)
    await db_session.flush()

    entity = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="Acme Corp",
        entity_type=EntityType.COMPANY,
        country="DE",
        role=EntityRole.BUYER,
    )
    db_session.add(entity)
    await db_session.commit()

    class BrokenYente:
        async def is_healthy(self) -> bool:
            return True

        async def match_entities_batch(self, entities, max_concurrent=5):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.services.screening_service.get_yente_client", lambda: BrokenYente())

    with pytest.raises(RuntimeError):
        await screen_invoice(db_session, invoice.id)

    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.SCREENING_FAILED
    assert invoice.compliance_score is None


@pytest.mark.asyncio
async def test_screening_uses_email_hints_from_invoice_text(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
        destination_country="DE",
        raw_text="Contact us at procurement@nuevo-continente.com for shipment updates.",
    )
    db_session.add(invoice)
    await db_session.flush()

    entity = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="Generic Buyer GmbH",
        entity_type=EntityType.COMPANY,
        country="DE",
        role=EntityRole.BUYER,
        email="operations@example.com",
    )
    db_session.add(entity)
    await db_session.commit()

    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def match_entities_batch(self, entities, max_concurrent=5):
            output = {}
            for e in entities:
                name = str(e["name"]).lower()
                if "nuevo continente" in name or "nuevocontinente" in name:
                    output[str(e["id"])] = [
                        YenteMatch(
                            dataset="us_ofac_sdn",
                            entity_id="nk-1",
                            matched_name="NUEVO CONTINENTE S.A.",
                            score=0.91,
                            listed_on=date(2026, 1, 1),
                            raw={"source": "test"},
                        )
                    ]
                else:
                    output[str(e["id"])] = []
            return output

    monkeypatch.setattr("app.services.screening_service.get_yente_client", lambda: FakeYente())

    updated = await screen_invoice(db_session, invoice.id)
    assert updated.status == InvoiceStatus.SCREENED
    assert updated.compliance_score == ComplianceScore.RED

    rows = (
        await db_session.execute(
            select(ScreeningResult).where(ScreeningResult.invoice_id == invoice.id)
        )
    ).scalars().all()
    assert any(r.status == MatchStatus.CONFIRMED_MATCH for r in rows)
    assert any(
        (r.raw_response or {}).get("query_source") == "raw_text_email"
        for r in rows
        if r.status != MatchStatus.CLEAR
    )


@pytest.mark.asyncio
async def test_screening_ignores_generic_email_hints(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
        destination_country="DE",
        raw_text="Buyer email: purchasing@atlaspetro.example",
    )
    db_session.add(invoice)
    await db_session.flush()

    buyer = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="Atlas Petro Services Ltd",
        entity_type=EntityType.COMPANY,
        country="DE",
        role=EntityRole.BUYER,
        email="purchasing@atlaspetro.example",
    )
    seller = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="Bilbao Marine Parts S.L.",
        entity_type=EntityType.COMPANY,
        country="ES",
        role=EntityRole.SELLER,
        email="export@bilbaomarine.example",
    )
    db_session.add_all([buyer, seller])
    await db_session.commit()

    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def match_entities_batch(self, entities, max_concurrent=5):
            out = {}
            for e in entities:
                name = str(e["name"]).lower()
                if "purchasing" in name:
                    out[str(e["id"])] = [
                        YenteMatch(
                            dataset="eu_fsf",
                            entity_id="eu-x",
                            matched_name="State Purchasing Organisation",
                            score=0.8,
                            listed_on=date(2026, 1, 1),
                            raw={"source": "test"},
                        )
                    ]
                else:
                    out[str(e["id"])] = []
            return out

    monkeypatch.setattr("app.services.screening_service.get_yente_client", lambda: FakeYente())

    updated = await screen_invoice(db_session, invoice.id)
    assert updated.status == InvoiceStatus.SCREENED
    assert updated.compliance_score == ComplianceScore.GREEN

    rows = (
        await db_session.execute(
            select(ScreeningResult).where(ScreeningResult.invoice_id == invoice.id)
        )
    ).scalars().all()
    assert not any(row.status == MatchStatus.POTENTIAL_MATCH for row in rows)


@pytest.mark.asyncio
async def test_screening_uses_raw_text_label_candidates(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
        destination_country="DE",
        raw_text=(
            "## COMMERCIAL INVOICE\\n"
            "Technical contact: Abdelmalek Droukdel\\n"
            "Buyer: Generic Imports Ltd\\n"
        ),
    )
    db_session.add(invoice)
    await db_session.flush()

    buyer = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="Generic Imports Ltd",
        entity_type=EntityType.COMPANY,
        country="DE",
        role=EntityRole.BUYER,
    )
    db_session.add(buyer)
    await db_session.commit()

    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def match_entities_batch(self, entities, max_concurrent=5):
            out = {}
            for e in entities:
                name = str(e["name"]).lower()
                if "abdelmalek droukdel" in name:
                    out[str(e["id"])] = [
                        YenteMatch(
                            dataset="us_ofac_sdn",
                            entity_id="ofac-1",
                            matched_name="ABDELMALEK DROUKDEL",
                            score=0.92,
                            listed_on=date(2026, 1, 1),
                            raw={"source": "test"},
                        )
                    ]
                else:
                    out[str(e["id"])] = []
            return out

    monkeypatch.setattr("app.services.screening_service.get_yente_client", lambda: FakeYente())

    updated = await screen_invoice(db_session, invoice.id)
    assert updated.status == InvoiceStatus.SCREENED
    assert updated.compliance_score == ComplianceScore.RED

    rows = (
        await db_session.execute(
            select(ScreeningResult).where(ScreeningResult.invoice_id == invoice.id)
        )
    ).scalars().all()
    assert any(row.status == MatchStatus.CONFIRMED_MATCH for row in rows)
    assert any(
        (row.raw_response or {}).get("query_source") == "raw_text_label"
        for row in rows
        if row.status != MatchStatus.CLEAR
    )


def test_normalize_candidate_name_filters_navigation_noise() -> None:
    noisy = (
        "Organization | Sercel Over menu News & Events Resources Job list "
        "Main navigation About Sercel"
    )
    assert _normalize_candidate_name(noisy) is None


def test_normalize_candidate_name_keeps_valid_long_sanctions_name() -> None:
    name = (
        "Main Centre for Special Technologies of the Main Directorate of the "
        "General Staff of the Armed Forces of the Russian Federation"
    )
    normalized = _normalize_candidate_name(name)
    assert normalized is not None
    assert "Main Centre for Special Technologies" in normalized
