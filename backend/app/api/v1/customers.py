"""Kunde-endepunkter."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Response, status

from app.core.database import SessionDep
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerRead,
    CustomerUpdate,
)
from app.services import customer_service

router = APIRouter()


@router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Opprett en ny kunde",
)
async def create_customer_endpoint(
    body: CustomerCreate,
    session: SessionDep,
) -> CustomerRead:
    customer = await customer_service.create_customer(session, body)
    return CustomerRead.model_validate(customer)


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List kunder med paginering og valgfritt søk",
)
async def list_customers_endpoint(
    session: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, description="Fritekst-søk i kundenavn"),
) -> CustomerListResponse:
    customers, total = await customer_service.list_customers(
        session, limit=limit, offset=offset, search=search
    )
    return CustomerListResponse(
        items=[CustomerRead.model_validate(c) for c in customers],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerRead,
    summary="Hent en spesifikk kunde",
)
async def get_customer_endpoint(
    customer_id: uuid.UUID,
    session: SessionDep,
) -> CustomerRead:
    customer = await customer_service.get_customer(session, customer_id)
    return CustomerRead.model_validate(customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerRead,
    summary="Oppdater en kunde (delvis)",
)
async def update_customer_endpoint(
    customer_id: uuid.UUID,
    body: CustomerUpdate,
    session: SessionDep,
) -> CustomerRead:
    customer = await customer_service.update_customer(session, customer_id, body)
    return CustomerRead.model_validate(customer)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Slett en kunde",
)
async def delete_customer_endpoint(
    customer_id: uuid.UUID,
    session: SessionDep,
) -> Response:
    """Sletter kunden.

    Invoices som peker til kunden beholder customer_id=NULL (ON DELETE SET NULL).
    """
    await customer_service.delete_customer(session, customer_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
