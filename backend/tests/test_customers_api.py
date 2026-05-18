"""API-tester for kunder."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_customer_crud_flow(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/api/v1/customers",
        json={
            "name": "Acme AS",
            "country": "no",
            "org_number": "123456789",
            "risk_level": "normal",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    customer_id = created["id"]
    assert created["name"] == "Acme AS"
    assert created["country"] == "NO"

    list_resp = await client.get("/api/v1/customers?limit=10&offset=0")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] == 1
    assert list_body["items"][0]["id"] == customer_id

    get_resp = await client.get(f"/api/v1/customers/{customer_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == customer_id

    patch_resp = await client.patch(
        f"/api/v1/customers/{customer_id}",
        json={"risk_level": "high"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["risk_level"] == "high"

    delete_resp = await client.delete(f"/api/v1/customers/{customer_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/v1/customers/{customer_id}")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["code"] == "NOT_FOUND"

