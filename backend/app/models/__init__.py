"""
SQLAlchemy-modeller.

Importer alle modeller her slik at Alembic autogenerate kan finne dem.
"""

from app.models.agreement import Agreement, AgreementCheckResult
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.entity import Entity, EntityRole, EntityType
from app.models.extended_screen_claim import ExtendedScreenClaim
from app.models.extended_screen_feedback import ExtendedScreenFeedback
from app.models.extended_screen_source import ExtendedScreenSource
from app.models.extended_screening import ExtendedScreenRun
from app.models.external_watchlist_entry import ExternalWatchlistEntry
from app.models.geocode_cache import GeocodeCache
from app.models.invoice import (
    ComplianceScore,
    Invoice,
    InvoiceDirection,
    InvoiceStatus,
)
from app.models.invoice_pipeline_event import InvoicePipelineEvent
from app.models.invoice_line import InvoiceLine
from app.models.rule import Rule, RuleSeverity, RuleVersion
from app.models.sanctions_list import SanctionsList
from app.models.sanctions_refresh_run import SanctionsRefreshRun
from app.models.screening import MatchStatus, ScreeningResult
from app.models.screening_run import ScreeningCandidate, ScreeningRun
from app.models.user_preference import UserPreference

__all__ = [
    "Agreement",
    "AgreementCheckResult",
    "AuditLog",
    "ComplianceScore",
    "Customer",
    "Entity",
    "EntityRole",
    "EntityType",
    "ExtendedScreenClaim",
    "ExtendedScreenFeedback",
    "ExtendedScreenRun",
    "ExtendedScreenSource",
    "ExternalWatchlistEntry",
    "GeocodeCache",
    "Invoice",
    "InvoiceDirection",
    "InvoicePipelineEvent",
    "InvoiceLine",
    "InvoiceStatus",
    "MatchStatus",
    "Rule",
    "RuleSeverity",
    "RuleVersion",
    "SanctionsList",
    "SanctionsRefreshRun",
    "ScreeningCandidate",
    "ScreeningResult",
    "ScreeningRun",
    "UserPreference",
]
