"""Pydantic-skjemaer for sanksjonsscreening-API-et."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.screening import MatchStatus


class ScreeningResultRead(BaseModel):
    """Ett screening-treff slik det returneres i API-et."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    entity_id: uuid.UUID
    dataset: str
    dataset_entity_id: str | None
    matched_name: str | None
    score: Decimal
    listed_on: date | None
    status: MatchStatus
    screened_at: datetime

    # Entitetsinfo for enkel visning (denormalisert fra Entity)
    entity_name: str | None = None
    entity_role: str | None = None
    match_explanation: str | None = None


class ScreeningResultsResponse(BaseModel):
    """Samling av alle screeningresultater for en invoice."""

    invoice_id: uuid.UUID
    compliance_score: str | None
    results: list[ScreeningResultRead]
    screened_at: datetime | None

    # Oppsummering
    total_entities: int
    confirmed_matches: int
    potential_matches: int
    clear: int


class ScreeningCandidateDebugRead(BaseModel):
    """Kandidatlinje brukt i screeningmotoren (debug)."""

    key: str
    entity_id: uuid.UUID
    entity_name: str | None = None
    entity_role: str | None = None
    candidate_name: str
    entity_type: str
    country: str | None = None
    source: str
    source_email: str | None = None
    primary: bool = False


class ScreeningCandidatesResponse(BaseModel):
    """Kandidater som blir sendt inn til screeningsok."""

    invoice_id: uuid.UUID
    run_id: uuid.UUID | None = None
    run_status: str | None = None
    run_started_at: datetime | None = None
    run_finished_at: datetime | None = None
    mode: str = "preview"
    total: int
    items: list[ScreeningCandidateDebugRead]


class ScreenRequest(BaseModel):
    """Foresporselen om a screene en invoice manuelt."""

    # Tom — lar alt bruke system-standard for enkelhets skyld
    pass


class YenteDatasetStatus(BaseModel):
    """Status for ett enkelt yente-datasett."""

    name: str
    title: str | None = None
    entity_count: int | None = None
    last_updated: str | None = None
    status: str  # "loaded" | "indexing" | "error"


class LocalSanctionsSourceStatus(BaseModel):
    """Status for lokal nedlasting/parsing av en sanksjonskilde."""

    source: str
    last_updated: datetime | None = None
    entry_count: int | None = None
    update_status: str
    error_message: str | None = None


class SanctionsRefreshRunStatus(BaseModel):
    """Nyeste kjorestatus for sanksjonsrefresh."""

    trigger: str
    status: str
    message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class ExternalSourceHealthStatus(BaseModel):
    """Health for eksterne datakilder brukt i utvidet screening."""

    source: str
    enabled: bool
    status: str
    entry_count: int | None = None
    last_updated: datetime | None = None
    error_message: str | None = None
    stale: bool = False


class SanctionsStatusResponse(BaseModel):
    """Status for yente-tjenesten og alle datasett."""

    yente_available: bool
    elasticsearch_available: bool
    elasticsearch_error: str | None = None
    yente_version: str | None = None
    datasets: list[YenteDatasetStatus]
    local_sources: list[LocalSanctionsSourceStatus] = Field(default_factory=list)
    external_sources: list[ExternalSourceHealthStatus] = Field(default_factory=list)
    refresh_schedule_time: str = "07:40"
    refresh_schedule_timezone: str = "Europe/Oslo"
    external_refresh_schedule_time: str = "07:45"
    last_refresh_run: SanctionsRefreshRunStatus | None = None


class SanctionsRefreshResponse(BaseModel):
    """Svar fra manuell datasett-oppdatering."""

    message: str
    datasets_triggered: list[str]


class SanctionedEntityRead(BaseModel):
    """Forenklet representasjon av en sanksjonert entitet fra yente."""

    id: str
    caption: str
    schema: str
    datasets: list[str]
    countries: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    first_seen: str | None = None
    last_seen: str | None = None
    last_change: str | None = None


class SanctionedEntityListResponse(BaseModel):
    """Paginert liste over sanksjonerte personer/selskaper."""

    items: list[SanctionedEntityRead]
    total: int
    total_relation: str
    limit: int
    offset: int
    query: str
    entity_type: str


class AdHocScreenEntity(BaseModel):
    """En entitet som skal screenes via POST /screen."""

    name: str
    entity_type: str = "company"
    country: str | None = None


class AdHocScreenRequest(BaseModel):
    """Request-body for ad hoc screening av entiteter."""

    entities: list[AdHocScreenEntity]


class AdHocScreenMatch(BaseModel):
    """Ett treff i ad hoc screening."""

    list: str
    score: float
    matched_name: str | None
    sanctions_type: str | None = None


class AdHocScreenEntityResult(BaseModel):
    """Resultat per innsendt entitet."""

    entity: str
    matches: list[AdHocScreenMatch]
    status: str


class AdHocScreenResponse(BaseModel):
    """Response-body for POST /screen."""

    results: list[AdHocScreenEntityResult]


class ExtendedScreenStartRequest(BaseModel):
    """Request for å starte utvidet screening på en entitet."""

    aggressiveness: int = Field(
        default=70,
        ge=0,
        le=100,
        description="0=konservativ, 100=aggressiv nettverksscreening.",
    )
    min_edge_confidence: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Min confidence for relasjoner som skal brukes i run-konklusjon.",
    )
    selected_only: bool = Field(
        default=True,
        description="Bruk kun kandidater markert som selected i den videre relasjonsvurderingen.",
    )
    sanctions_near_only: bool = Field(
        default=False,
        description="Begrens run til sanksjonsnaere relasjonstyper.",
    )
    enable_brreg: bool = Field(
        default=True,
        description="Aktiver Brreg-oppslag (norske roller/selskapsdata).",
    )
    enable_uk_sanctions: bool = Field(
        default=True,
        description="Aktiver UK sanctions CSV i ekstern match.",
    )
    enable_world_bank_debarred: bool = Field(
        default=True,
        description="Aktiver World Bank debarred-liste i ekstern match.",
    )
    enable_ai_entity_research: bool = Field(
        default=True,
        description=(
            "Aktiver AI-assistert innhenting av eierskap/ledelse fra eksterne kilder."
        ),
    )
    enable_ai_web_search: bool = Field(
        default=True,
        description="Aktiver bredt websok (DuckDuckGo) som ekstra evidensgrunnlag.",
    )


class ExtendedScreenRunConfig(BaseModel):
    """Persistérbar konfig for én utvidet-screening-run."""

    min_edge_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    selected_only: bool = True
    sanctions_near_only: bool = False
    enable_brreg: bool = True
    enable_uk_sanctions: bool = True
    enable_world_bank_debarred: bool = True
    enable_ai_entity_research: bool = True
    enable_ai_web_search: bool = True


class ExtendedScreenRunRead(BaseModel):
    """Kompakt visning av én utvidet-screening-kjøring."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    invoice_id: uuid.UUID
    entity_id: uuid.UUID
    aggressiveness: int
    status: str
    summary_risk: str | None = None
    summary_text: str | None = None
    error_message: str | None = None
    run_config: ExtendedScreenRunConfig | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class ExtendedScreenRunResponse(ExtendedScreenRunRead):
    """Detaljert visning av én utvidet-screening-kjøring."""

    result_payload: dict | None = None


class ExtendedScreenFeedbackCreate(BaseModel):
    """Opprett analytiker-feedback på en run."""

    feedback_label: str = Field(
        pattern="^(false_positive|good_hit)$",
        description="Analytikervurdering av treff/signal.",
    )
    target_qid: str | None = Field(default=None, max_length=64)
    target_name: str | None = Field(default=None, max_length=512)
    note: str | None = Field(default=None, max_length=1024)


class ExtendedScreenFeedbackRead(BaseModel):
    """Returnert feedback-rad for utvidet screening."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    invoice_id: uuid.UUID
    entity_id: uuid.UUID
    feedback_label: str
    target_qid: str | None = None
    target_name: str | None = None
    note: str | None = None
    created_at: datetime


class ExtendedScreenSourceRead(BaseModel):
    """Persisted kilde brukt i utvidet screening."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    invoice_id: uuid.UUID
    entity_id: uuid.UUID
    provider: str
    source_url: str
    source_title: str | None = None
    source_domain: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    raw_payload: dict | None = None


class ExtendedScreenClaimRead(BaseModel):
    """Persisted claim + evidens brukt i utvidet screening."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    invoice_id: uuid.UUID
    entity_id: uuid.UUID
    claim_type: str
    claim_subject: str
    claim_object: str
    confidence: float | None = None
    verification_status: str
    source_provider: str
    source_url: str | None = None
    quoted_text: str | None = None
    raw_payload: dict | None = None
    created_at: datetime


class PipelineStageSummary(BaseModel):
    """Aggregert status per pipeline-steg."""

    stage: str
    in_progress: int
    stuck: int
    failed: int
    completed_last_window: int


class PipelineLatencySummary(BaseModel):
    """Latency-SLA for en del av pipelinen."""

    metric: str
    p50_seconds: float | None = None
    p95_seconds: float | None = None
    average_seconds: float | None = None


class PipelineMetricsResponse(BaseModel):
    """Overordnet driftsbilde for ingest/screening-pipeline."""

    generated_at: datetime
    lookback_hours: int
    total_invoices: int
    total_invoices_last_window: int
    staged: list[PipelineStageSummary]
    latencies: list[PipelineLatencySummary]
    alerts: list[str] = Field(default_factory=list)


class PipelineRecoveryItem(BaseModel):
    """Invoice som krever manuell/automatisk recovery."""

    invoice_id: uuid.UUID
    invoice_number: str | None = None
    original_filename: str | None = None
    status: str
    compliance_score: str | None = None
    updated_at: datetime
    minutes_in_status: int
    reason: str | None = None


class PipelineRecoveryResponse(BaseModel):
    """Liste over recoverable invoices."""

    generated_at: datetime
    stale_minutes: int
    total: int
    items: list[PipelineRecoveryItem]


class PipelineRecoveryActionResponse(BaseModel):
    """Svar etter retry/recovery-kommando."""

    invoice_id: uuid.UUID
    target: str
    message: str
