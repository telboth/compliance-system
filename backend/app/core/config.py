"""
Sentral applikasjonskonfigurasjon.

Alle innstillinger leses fra miljøvariabler via Pydantic Settings. Hardkodede
verdier i forretningslogikken er forbudt — alle terskler, URL-er og
miljøavhengige verdier skal hentes herfra.

Filprioritet (siste vinner):
  1. .env       — ikke-sensitive innstillinger
  2. .secrets   — API-nøkler og hemmeligheter (aldri i git)
  3. Miljøvariabler — overstyrer begge filene
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Finn repo-roten (to nivåer opp fra denne filen: core → app → backend → repo-rot).
_REPO_ROOT = Path(__file__).parent.parent.parent.parent


class Settings(BaseSettings):
    """Applikasjonsinnstillinger lastet fra .env og .secrets."""

    model_config = SettingsConfigDict(
        env_file=[
            str(_REPO_ROOT / ".env"),
            str(_REPO_ROOT / ".secrets"),
        ],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Applikasjon
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    app_secret_key: SecretStr = Field(default=SecretStr("change-me"))
    app_api_v1_prefix: str = "/api/v1"
    app_name: str = "XLENT Compliance"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://xlent:xlent_dev_password@postgres:5432/xlent_compliance",
        description="SQLAlchemy async URL — bruk asyncpg-driver.",
    )

    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"
    celery_timezone: str = "Europe/Oslo"
    # Velg om bakgrunnsjobber skal dispatches via Celery i stedet for FastAPI BackgroundTasks.
    use_celery_background: bool = False

    # Daglig automatisk sanksjonsoppdatering (Celery Beat).
    sanctions_refresh_hour: int = 7
    sanctions_refresh_minute: int = 40
    # Daglig oppdatering av eksterne watchlists (UK sanctions).
    external_source_refresh_hour: int = 7
    external_source_refresh_minute: int = 45
    external_source_stale_hours: int = 36
    # Månedlig oppdatering av World Bank Debarred Firms and Individuals.
    world_bank_debarred_refresh_hour: int = 3
    world_bank_debarred_refresh_minute: int = 15
    world_bank_debarred_refresh_day_of_month: int = 1
    world_bank_debarred_stale_days: int = 45

    # LLM — nøkler leses fra .secrets
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    openai_api_key: SecretStr = Field(default=SecretStr(""))
    llm_primary_provider: Literal["anthropic", "openai", "ollama"] = "openai"
    llm_primary_model: str = "gpt-4o"
    llm_fallback_provider: Literal["anthropic", "openai", "ollama"] = "anthropic"
    llm_fallback_model: str = "claude-sonnet-4-6"

    # Ollama — lokal LLM på maskinen til brukeren
    # Fra Docker-container: host.docker.internal:11434
    # Fra lokal prosess: localhost:11434
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_timeout_seconds: int = 120
    # GPU-konfigmasjon for Ollama:
    #   None  → auto-detekter (GPU brukes hvis tilgjengelig)
    #   True  → tving GPU-kjøring (num_gpu=-1, alle lag til GPU)
    #   False → tving CPU-kjøring (num_gpu=0)
    ollama_use_gpu: bool | None = None

    # GPU — OCR-akselerasjon (EasyOCR via Docling)
    #   None  → auto-detekter GPU og bruk den hvis tilgjengelig
    #   True  → tving GPU (feil hvis ingen GPU finnes)
    #   False → tving CPU selv om GPU er tilgjengelig
    ocr_use_gpu: bool | None = None

    # Docling PDF-parsing
    # "standard"   — Doclings innebygde pipeline (TableFormer osv.), ingen API-nøkkel.
    # "multimodal" — OpenAI vision-API for sideforståelse, krever OPENAI_API_KEY.
    docling_pipeline: Literal["standard", "multimodal"] = "standard"
    docling_vlm_model: str = "gpt-4o"

    # Lagring
    upload_dir: Path = Path("/data/uploads")
    max_upload_size_mb: int = 25

    # Forretningsregler
    # Felter med konfidens under denne terskelen eskaleres til manuell review.
    # Jf. arkitekturprinsipp 2 i SKILL.md: «Konfidens er eksplisitt».
    confidence_threshold: float = 0.8

    # Auto-ekstraksjon: start LLM-ekstraksjon automatisk etter vellykket parsing.
    # True (standard): ekstraksjon starter i bakgrunnen rett etter parsing er ferdig.
    # True: ekstraksjon starter i bakgrunnen rett etter parsing er ferdig.
    auto_extract_after_parse: bool = True
    # Hard timeout rundt Docling-parsing for a unnga evig spinner ved heng.
    parsing_timeout_seconds: int = 180
    # Hard timeout rundt samlet ekstraksjonskall (LLM + heuristikk).
    extraction_timeout_seconds: int = 180

    # Sanksjonsscreening — yente OpenSanctions
    yente_url: str = "http://yente:8000"
    yente_update_token: str = ""
    elasticsearch_url: str = "http://elasticsearch:9200"
    opencorporates_api_token: str = ""
    extended_screen_ai_model: str = "gpt-4o-mini"
    extended_screen_ai_timeout_seconds: int = 45
    extended_screen_run_timeout_seconds: int = 240

    # Kildevekter for risikologikk (0.0-1.0 multiplikator på match-score).
    source_weight_yente: float = 1.0
    source_weight_uk_sanctions: float = 0.95
    source_weight_world_bank_debarred: float = 0.9

    # Terskler for match-klassifisering (score fra yente, 0.0-1.0)
    screening_confirmed_threshold: float = Field(
        default=0.79,
        description="Score >= denne → confirmed_match → RED compliance_score.",
    )
    screening_match_threshold: float = Field(
        default=0.70,
        description="Score >= denne (og < confirmed) → potential_match → YELLOW.",
    )
    # Timeout rundt hele yente batch-kallet (sekunder).
    screening_match_timeout_seconds: int = 90
    # Beskyttelse mot ekstremt mange kandidater som gjør screening treg.
    screening_max_candidates: int = 60
    # Celery timeouts for screening-task.
    screening_task_soft_timeout_seconds: int = 120
    screening_task_hard_timeout_seconds: int = 150

    # Auto-screening: start sanksjonsscreening automatisk etter vellykket ekstraksjon.
    # False (standard): bruker klikker «Screen» manuelt.
    # True: screening starter asynkront rett etter extraction er ferdig.
    auto_screen_after_extract: bool = True
    screening_watchdog_enabled: bool = True
    screening_watchdog_stale_minutes: int = 3
    screening_watchdog_batch_size: int = 20
    screening_watchdog_interval_minutes: int = 1
    # Myk lås i review-kø: claim anses som stale etter N minutter.
    review_claim_stale_minutes: int = 30

    # Invoice RAG-søk (hybrid BM25 + vector)
    rag_embedding_model: str = "text-embedding-3-small"
    rag_embedding_dimensions: int = 1536
    rag_chunk_size_chars: int = 1000
    rag_chunk_overlap_chars: int = 150
    rag_top_k: int = 10
    rag_llm_model: str = "gpt-4o-mini"
    rag_llm_timeout_seconds: int = 45

    # Forsendelseskart / geokoding
    geocode_provider: Literal["nominatim"] = "nominatim"
    geocode_nominatim_url: str = "https://nominatim.openstreetmap.org/search"
    geocode_timeout_seconds: int = 12
    geocode_user_agent: str = "xlent-compliance/0.1 (contact: compliance@xlent.no)"
    geocode_max_external_lookups_per_request: int = 20

    # Regulatorisk Radar — RSS/Atom-feed aggregator
    regulatory_radar_enabled: bool = True
    # Timer for Celery Beat — daglig oppdatering
    regulatory_radar_refresh_hour: int = 6
    regulatory_radar_refresh_minute: int = 30
    # HTTP-timeout per feed-kall (sekunder)
    regulatory_radar_feed_timeout_seconds: int = 30

    # CORS
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Konverter kommaseparert CORS-streng til liste."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def openai_api_key_value(self) -> str:
        """Returnerer OpenAI-nøkkelen som klartekst (for bruk i klienter)."""
        return self.openai_api_key.get_secret_value()

    @property
    def anthropic_api_key_value(self) -> str:
        """Returnerer Anthropic-nøkkelen som klartekst (for bruk i klienter)."""
        return self.anthropic_api_key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    """Hent applikasjonsinnstillinger som en cached singleton."""
    return Settings()


def get_secrets_path() -> Path:
    """Returnerer absolutt sti til .secrets-filen (repo-rot)."""
    return _REPO_ROOT / ".secrets"
