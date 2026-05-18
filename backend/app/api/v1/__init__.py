"""API v1 — endepunktrutere."""

from fastapi import APIRouter

from app.api.v1 import (
    audit,
    agreements,
    customers,
    dashboard,
    health,
    hs_codes,
    invoices,
    models,
    notifications,
    report,
    rules,
    sanctions,
    search,
    shipments,
    watchlist,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(shipments.router, prefix="/shipments", tags=["shipments"])

# Sanksjonsscreening — per-invoice under /invoices, admin under /sanctions
api_router.include_router(
    sanctions.invoice_router,
    prefix="/invoices",
    tags=["sanctions"],
)
api_router.include_router(
    sanctions.admin_router,
    prefix="/sanctions",
    tags=["sanctions"],
)
api_router.include_router(
    sanctions.public_router,
    tags=["sanctions"],
)

# Audit-logg (hash-kjedet) — per-invoice
api_router.include_router(
    audit.router,
    prefix="/invoices",
    tags=["audit"],
)

# Regelmotor (YAML)
api_router.include_router(rules.router, prefix="/rules", tags=["rules"])

# Rammeavtaler
api_router.include_router(agreements.router, prefix="/agreements", tags=["agreements"])
api_router.include_router(
    agreements.invoice_check_router,
    prefix="/invoices",
    tags=["agreements"],
)

# Dashboard / statistikk
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])

# In-app varsler
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])

# Compliance-rapport (HTML for print/PDF) — per-invoice
api_router.include_router(report.router, prefix="/invoices", tags=["report"])

# HS-kode klassifisering (statisk oppslagstabell)
api_router.include_router(hs_codes.router, prefix="/hs-codes", tags=["hs-codes"])

# Intern sperreliste
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
