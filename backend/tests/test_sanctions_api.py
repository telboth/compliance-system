"""API-tester for sanksjonsendepunkter."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient

from app.models.entity import Entity, EntityRole, EntityType
from app.models.extended_screening import ExtendedScreenRun
from app.models.invoice import Invoice, InvoiceDirection, InvoiceStatus
from app.models.sanctions_refresh_run import SanctionsRefreshRun
from app.sanctions.yente_client import YenteMatch, YenteSearchEntity, YenteSearchResult


@pytest.mark.asyncio
async def test_sanctions_status_returns_unavailable_when_yente_down(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeYente:
        async def is_healthy(self) -> bool:
            return False

    monkeypatch.setattr("app.api.v1.sanctions.get_yente_client", lambda: FakeYente())

    response = await client.get("/api/v1/sanctions/status")
    assert response.status_code == 200
    body = response.json()
    assert body["yente_available"] is False
    assert "elasticsearch_available" in body
    assert body["datasets"] == []
    assert "refresh_schedule_time" in body
    assert "refresh_schedule_timezone" in body
    assert body["last_refresh_run"] is None


@pytest.mark.asyncio
async def test_sanctions_status_returns_last_refresh_run(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeYente:
        async def is_healthy(self) -> bool:
            return False

    row = SanctionsRefreshRun(
        trigger="scheduled",
        status="success",
        message="Sanksjonsoppdatering trigget.",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.add(row)
    await db_session.commit()

    monkeypatch.setattr("app.api.v1.sanctions.get_yente_client", lambda: FakeYente())

    response = await client.get("/api/v1/sanctions/status")
    assert response.status_code == 200
    body = response.json()
    assert body["last_refresh_run"] is not None
    assert body["last_refresh_run"]["trigger"] == "scheduled"
    assert body["last_refresh_run"]["status"] == "success"


@pytest.mark.asyncio
async def test_start_screening_accepts_extracted_invoice(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
    )
    db_session.add(invoice)
    await db_session.commit()

    async def _noop(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.api.v1.sanctions._run_screening_background", _noop)

    response = await client.post(f"/api/v1/invoices/{invoice.id}/screen")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["invoice_id"] == str(invoice.id)

    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.SCREENING


@pytest.mark.asyncio
async def test_start_screening_accepts_screening_failed_invoice(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.SCREENING_FAILED,
    )
    db_session.add(invoice)
    await db_session.commit()

    async def _noop(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.api.v1.sanctions._run_screening_background", _noop)

    response = await client.post(f"/api/v1/invoices/{invoice.id}/screen")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["invoice_id"] == str(invoice.id)
    assert body["message"] == "Screening startet"

    await db_session.refresh(invoice)
    assert invoice.status == InvoiceStatus.SCREENING


@pytest.mark.asyncio
async def test_start_screening_is_idempotent_while_screening(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.SCREENING,
    )
    db_session.add(invoice)
    await db_session.commit()

    async def _boom(*args, **kwargs) -> None:
        raise AssertionError("Background task should not be scheduled when already screening")

    monkeypatch.setattr("app.api.v1.sanctions._run_screening_background", _boom)

    response = await client.post(f"/api/v1/invoices/{invoice.id}/screen")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["invoice_id"] == str(invoice.id)
    assert body["message"] == "Screening er allerede i gang"


@pytest.mark.asyncio
async def test_start_screening_requeues_stale_screening(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.SCREENING,
    )
    db_session.add(invoice)
    await db_session.commit()

    # Simuler en hengende jobb eldre enn stale-grensen.
    invoice.updated_at = datetime.now(UTC) - timedelta(minutes=10)
    await db_session.commit()

    async def _noop(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.api.v1.sanctions._run_screening_background", _noop)

    response = await client.post(f"/api/v1/invoices/{invoice.id}/screen")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["invoice_id"] == str(invoice.id)
    assert body["message"] == "Screening startet"


@pytest.mark.asyncio
async def test_start_screening_rejects_wrong_status(
    client: AsyncClient,
    db_session,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.UPLOADED,
    )
    db_session.add(invoice)
    await db_session.commit()

    response = await client.post(f"/api/v1/invoices/{invoice.id}/screen")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_screening_candidates_debug_endpoint(
    client: AsyncClient,
    db_session,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.EXTRACTED,
        raw_text="Technical contact: Abdelmalek Droukdel",
    )
    db_session.add(invoice)
    await db_session.flush()

    entity = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="Levant Engineering Stores FZE",
        entity_type=EntityType.COMPANY,
        role=EntityRole.BUYER,
        country="AE",
        email="orders@levantstores.example",
    )
    db_session.add(entity)
    await db_session.commit()

    response = await client.get(f"/api/v1/invoices/{invoice.id}/screening/candidates")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["invoice_id"] == str(invoice.id)
    assert body["total"] >= 1
    assert any(item["source"] in {"entity_name", "entity_email", "raw_text_label"} for item in body["items"])


@pytest.mark.asyncio
async def test_list_sanctioned_entities_company(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def search_entities(self, **kwargs):
            assert kwargs["schema"] == "LegalEntity"
            return YenteSearchResult(
                items=[
                    YenteSearchEntity(
                        id="E1",
                        caption="ACME AS",
                        schema="Organization",
                        datasets=["eu_fsf"],
                        countries=["no"],
                        topics=["sanction"],
                    )
                ],
                total=1,
                total_relation="eq",
                limit=kwargs["limit"],
                offset=kwargs["offset"],
            )

    monkeypatch.setattr("app.api.v1.sanctions.get_yente_client", lambda: FakeYente())

    response = await client.get("/api/v1/sanctions/entities?entity_type=company&limit=20&offset=0")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entity_type"] == "company"
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["caption"] == "ACME AS"


@pytest.mark.asyncio
async def test_list_sanctioned_entities_all_filters_person_and_company(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def search_entities(self, **kwargs):
            assert kwargs["schema"] == "Thing"
            return YenteSearchResult(
                items=[
                    YenteSearchEntity(id="P1", caption="Jane Doe", schema="Person"),
                    YenteSearchEntity(id="C1", caption="ACME AS", schema="Organization"),
                    YenteSearchEntity(id="V1", caption="VESSEL X", schema="Vessel"),
                ],
                total=3,
                total_relation="eq",
                limit=kwargs["limit"],
                offset=kwargs["offset"],
            )

    monkeypatch.setattr("app.api.v1.sanctions.get_yente_client", lambda: FakeYente())

    response = await client.get("/api/v1/sanctions/entities?entity_type=all&limit=10&offset=0")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entity_type"] == "all"
    assert [item["id"] for item in body["items"]] == ["P1", "C1"]


@pytest.mark.asyncio
async def test_ad_hoc_screen_endpoint_flags_matches(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def match_entities_batch(self, entities, max_concurrent=5):
            return {
                "0": [
                    YenteMatch(
                        dataset="us_ofac_sdn",
                        entity_id="E1",
                        matched_name="ROSNEFT",
                        score=0.8,
                        listed_on=None,
                        raw={},
                    )
                ]
            }

    monkeypatch.setattr("app.api.v1.sanctions.get_yente_client", lambda: FakeYente())

    response = await client.post(
        "/api/v1/screen",
        json={"entities": [{"name": "Rosneft Procurement", "entity_type": "company"}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["status"] == "flagged"
    assert body["results"][0]["matches"][0]["list"] == "us_ofac_sdn"


@pytest.mark.asyncio
async def test_ad_hoc_screen_endpoint_returns_clear_without_match(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeYente:
        async def is_healthy(self) -> bool:
            return True

        async def match_entities_batch(self, entities, max_concurrent=5):
            return {"0": []}

    monkeypatch.setattr("app.api.v1.sanctions.get_yente_client", lambda: FakeYente())

    response = await client.post(
        "/api/v1/screen",
        json={"entities": [{"name": "Acme AS", "entity_type": "company"}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["results"][0]["status"] == "clear"


@pytest.mark.asyncio
async def test_start_extended_screening_creates_run(
    client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.SCREENED,
    )
    db_session.add(invoice)
    await db_session.flush()

    entity = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="ACME AS",
        entity_type=EntityType.COMPANY,
        role=EntityRole.BUYER,
        country="NO",
    )
    db_session.add(entity)
    await db_session.commit()

    async def _noop(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr("app.api.v1.sanctions._run_extended_screen_background", _noop)

    response = await client.post(
        f"/api/v1/invoices/{invoice.id}/entities/{entity.id}/extended-screen",
        json={"aggressiveness": 65},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["invoice_id"] == str(invoice.id)
    assert body["entity_id"] == str(entity.id)
    assert body["aggressiveness"] == 65
    assert body["status"] == "queued"


@pytest.mark.asyncio
async def test_get_extended_screening_status(
    client: AsyncClient,
    db_session,
) -> None:
    invoice = Invoice(
        id=uuid.uuid4(),
        direction=InvoiceDirection.INCOMING,
        pdf_path="tests/fixtures/invoice.pdf",
        status=InvoiceStatus.SCREENED,
    )
    db_session.add(invoice)
    await db_session.flush()

    entity = Entity(
        id=uuid.uuid4(),
        invoice_id=invoice.id,
        name="ACME AS",
        entity_type=EntityType.COMPANY,
        role=EntityRole.BUYER,
        country="NO",
    )
    db_session.add(entity)
    await db_session.flush()

    run = ExtendedScreenRun(
        invoice_id=invoice.id,
        entity_id=entity.id,
        aggressiveness=50,
        status="completed",
        summary_risk="low",
        summary_text="MVP: ingen funn.",
        result_payload={"summary": {"risk_level": "low"}},
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.add(run)
    await db_session.commit()

    response = await client.get(
        f"/api/v1/invoices/{invoice.id}/entities/{entity.id}/extended-screen/{run.id}",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == str(run.id)
    assert body["status"] == "completed"
    assert body["summary_risk"] == "low"
