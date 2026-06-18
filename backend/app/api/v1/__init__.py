"""API v1 — endepunktrutere."""

from fastapi import APIRouter

from app.api.v1 import (
    audit,
    agreements,
    ai_governance,
    audit_plans,
    catch_all,
    config,
    control_effectiveness,
    customers,
    policies,
    dashboard,
    export_control,
    health,
    hs_codes,
    invoices,
    kri,
    models,
    notifications,
    regulatory_radar,
    report,
    risk,
    rules,
    sanctions,
    search,
    shipments,
    vendors,
    watchlist,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
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

# Regulatorisk Radar
api_router.include_router(
    regulatory_radar.router,
    prefix="/regulatory-radar",
    tags=["regulatory-radar"],
)

# Vendor Register
api_router.include_router(vendors.router, prefix="/vendors", tags=["vendors"])

# KRI Dashboard
api_router.include_router(kri.router, prefix="/kri", tags=["kri"])

# Control Effectiveness
api_router.include_router(
    control_effectiveness.router,
    prefix="/control-deviations",
    tags=["control-effectiveness"],
)

# Eksportkontroll — Vareliste I/II listematch
api_router.include_router(
    export_control.router,
    prefix="/export-control",
    tags=["export-control"],
)

# Catch-all — sluttbruker-/sluttbruk-screening
api_router.include_router(
    catch_all.router,
    prefix="/catch-all",
    tags=["catch-all"],
)

# Policy Management
api_router.include_router(policies.router, prefix="/policies", tags=["policies"])

# Audit Plan Management
api_router.include_router(audit_plans.router, prefix="/audit-plans", tags=["audit-plans"])

# AI Governance
api_router.include_router(ai_governance.router, prefix="/ai-governance", tags=["ai-governance"])

# Risikokvantifisering — per-invoice under /invoices, admin-bulk under /risk
api_router.include_router(risk.invoice_router, prefix="/invoices", tags=["risk"])
api_router.include_router(risk.admin_router, prefix="/risk", tags=["risk"])
