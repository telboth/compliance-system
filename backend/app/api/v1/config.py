"""
Konfigurasjon-endepunkter — sjekk og oppdatering av API-nøkler.

GET  /config/keys/status   Åpen (ingen auth) — boolsk status per nøkkel.
                           Ingen nøkkelverdier eksponeres noensinne.
POST /config/keys          Admin-only — skriver nøkler til .secrets og
                           oppdaterer innstillinger live uten restart.
"""

from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.core.config import get_secrets_path, get_settings
from app.core.logging import get_logger
from app.core.security import require_roles

logger = get_logger(__name__)
router = APIRouter(tags=["config"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class KeysStatusResponse(BaseModel):
    """Boolsk tilstedeværelse per nøkkel — aldri selve verdien."""
    anthropic: bool
    openai: bool


class KeysUpdateRequest(BaseModel):
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None


# ── Endepunkter ───────────────────────────────────────────────────────────────

@router.get("/keys/status", response_model=KeysStatusResponse)
async def get_keys_status() -> KeysStatusResponse:
    """
    Sjekker om API-nøkler er konfigurert.
    Åpent endepunkt — kalles av frontend ved oppstart uten å kreve auth.
    """
    s = get_settings()
    return KeysStatusResponse(
        anthropic=bool(s.anthropic_api_key_value),
        openai=bool(s.openai_api_key_value),
    )


@router.post(
    "/keys",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def update_keys(
    body: KeysUpdateRequest,
    _actor=Depends(require_roles("admin")),
) -> Response:
    """
    Lagrer API-nøkler til .secrets og oppdaterer konfigurasjonen live.

    Gjør tre ting for at endringen virker umiddelbart uten restart:
    1. Skriver til .secrets (persistent over neste restart).
    2. Setter os.environ (gjelder inneværende prosess).
    3. Tømmer get_settings() sin lru_cache slik at neste kall laster nye verdier.
    """
    anthropic = (body.anthropic_api_key or "").strip()
    openai_key = (body.openai_api_key or "").strip()

    if not anthropic and not openai_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Minst én nøkkel (anthropic_api_key eller openai_api_key) må oppgis.",
        )

    updates: dict[str, str] = {}
    if anthropic:
        updates["ANTHROPIC_API_KEY"] = anthropic
    if openai_key:
        updates["OPENAI_API_KEY"] = openai_key

    # 1. Skriv til .secrets
    _write_secrets(updates)

    # 2. Oppdater prosessens miljøvariabler
    for env_key, val in updates.items():
        os.environ[env_key] = val

    # 3. Tøm lru_cache — neste get_settings()-kall laster nye verdier
    get_settings.cache_clear()

    logger.info("api_keys_updated", updated_keys=list(updates.keys()))

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Intern hjelpefunksjon ─────────────────────────────────────────────────────

def _write_secrets(updates: dict[str, str]) -> None:
    """
    Oppdaterer eksisterende KEY=value-linjer i .secrets på stedet.
    Nøkler som ikke fantes legges til på slutten.
    Kommentarer og blanke linjer beholdes uendret.
    """
    secrets_path = get_secrets_path()
    lines: list[str] = []
    already_written: set[str] = set()

    if secrets_path.exists():
        for line in secrets_path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Z_][A-Z0-9_]*)\s*=", line)
            if m and m.group(1) in updates:
                key = m.group(1)
                lines.append(f"{key}={updates[key]}")
                already_written.add(key)
            else:
                lines.append(line)

    # Legg til nøkler som ikke fantes fra før
    for key, val in updates.items():
        if key not in already_written:
            lines.append(f"{key}={val}")

    secrets_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
