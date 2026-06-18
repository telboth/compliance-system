"""Forretningslogikk for kundehåndtering."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models.customer import Customer
from app.schemas.customer import CustomerCreate, CustomerUpdate

logger = get_logger(__name__)


async def create_customer(session: AsyncSession, data: CustomerCreate) -> Customer:
    """Opprett en ny kunde."""
    customer = Customer(
        name=data.name,
        country=data.country.upper() if data.country else None,
        org_number=data.org_number,
        risk_level=data.risk_level,
    )
    session.add(customer)
    await session.commit()
    await session.refresh(customer)
    logger.info("customer_created", customer_id=str(customer.id), name=customer.name)
    return customer


async def get_customer(session: AsyncSession, customer_id: uuid.UUID) -> Customer:
    """Hent en kunde. Reiser NotFoundError hvis ikke funnet."""
    result = await session.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()
    if customer is None:
        raise NotFoundError(
            "Kunde ikke funnet.",
            details={"customer_id": str(customer_id)},
        )
    return customer


async def list_customers(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> tuple[list[Customer], int]:
    """List kunder med paginering og valgfritt navnesøk."""
    count_stmt = select(func.count()).select_from(Customer)
    list_stmt = select(Customer).order_by(Customer.name.asc())

    if search:
        pattern = f"%{search}%"
        count_stmt = count_stmt.where(Customer.name.ilike(pattern))
        list_stmt = list_stmt.where(Customer.name.ilike(pattern))

    total = (await session.execute(count_stmt)).scalar_one()
    list_stmt = list_stmt.limit(limit).offset(offset)
    customers = list((await session.execute(list_stmt)).scalars().all())
    return customers, total


async def update_customer(
    session: AsyncSession,
    customer_id: uuid.UUID,
    data: CustomerUpdate,
) -> Customer:
    """Oppdater en eksisterende kunde (PATCH — kun angitte felt)."""
    customer = await get_customer(session, customer_id)
    update_dict = data.model_dump(exclude_none=True)
    for field, value in update_dict.items():
        if field == "country" and isinstance(value, str):
            value = value.upper()
        setattr(customer, field, value)
    await session.commit()
    await session.refresh(customer)
    logger.info(
        "customer_updated",
        customer_id=str(customer_id),
        fields=list(update_dict.keys()),
    )
    return customer


async def delete_customer(session: AsyncSession, customer_id: uuid.UUID) -> None:
    """Slett en kunde (hard delete — invoices beholder customer_id=NULL via ON DELETE SET NULL)."""
    customer = await get_customer(session, customer_id)
    await session.delete(customer)
    await session.commit()
    logger.info("customer_deleted", customer_id=str(customer_id))
