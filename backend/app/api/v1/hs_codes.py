"""HS-kode klassifiserings-API."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.hs_code_service import classify

router = APIRouter()


class HSClassificationOut(BaseModel):
    code: str
    chapter: str
    chapter_description: str
    heading: str | None
    heading_description: str | None
    risk_level: str | None
    risk_reason: str | None
    is_controlled: bool
    dual_use_flag: bool


@router.get(
    "/classify",
    response_model=HSClassificationOut | None,
    summary="Klassifiser en HS-kode og returner risikovurdering",
)
async def classify_hs_code(
    code: str = Query(..., description="HS-kode (2–10 siffer, punktum og mellomrom tillatt)"),
) -> HSClassificationOut | None:
    """Slår opp risikovurdering for en HS-kode basert på statisk tabell.

    Returnerer `null` hvis koden er ugyldig eller tom.
    """
    result = classify(code)
    if result is None:
        return None
    return HSClassificationOut(
        code=result.code,
        chapter=result.chapter,
        chapter_description=result.chapter_description,
        heading=result.heading,
        heading_description=result.heading_description,
        risk_level=result.risk_level,
        risk_reason=result.risk_reason,
        is_controlled=result.is_controlled,
        dual_use_flag=result.dual_use_flag,
    )
