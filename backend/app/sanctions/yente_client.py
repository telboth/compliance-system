"""
Asynkron HTTP-klient mot yente OpenSanctions-tjenesten.

Yente eksponerer et REST API for fuzzy entitetsoppslag.
Viktigste endepunkter vi bruker:
  GET  /healthz                      — helsesjekk
  GET  /datasets                     — liste datasett og status
  POST /match/{dataset}              — match en entitet mot ett datasett
  POST /match                        — match mot alle aktive datasett

Matching POST-kropp (FtM-format):
  {
    "queries": {
      "<query_id>": {
        "schema": "Person" | "Company" | "Vessel",
        "properties": { "name": ["Acme Corp"], "country": ["NO"] }
      }
    }
  }

Respons-format (forenklet):
  {
    "responses": {
      "<query_id>": {
        "results": [
          {
            "id":        "NK-xyz",
            "caption":   "ACME CORP",
            "schema":    "Company",
            "score":     0.94,
            "datasets":  ["eu_fsf"],
            "properties": { ... }
          }
        ]
      }
    }
  }
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Yente FtM-skjema per entitetstype.
_FTM_SCHEMA: dict[str, str] = {
    "person": "Person",
    "company": "Company",
    "vessel": "Vessel",
    "aircraft": "Vessel",  # yente har ikke eget Aircraft-skjema
}

# Timeout for enkeltoppslag — yente er rask (<2 s) men datasett-nedlasting kan ta tid.
_REQUEST_TIMEOUT = 10.0


@dataclass
class YenteMatch:
    """Ett treff fra yente-oppslaget."""

    dataset: str
    entity_id: str | None
    matched_name: str | None
    score: float
    listed_on: date | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class YenteDataset:
    """Metadata for ett yente-datasett."""

    name: str
    title: str | None
    entity_count: int | None
    last_updated: str | None
    status: str  # "loaded" | "indexing" | "error" | "unknown"


@dataclass
class YenteSearchEntity:
    """Forenklet entitet fra /search-endepunktet."""

    id: str
    caption: str
    schema: str
    datasets: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    first_seen: str | None = None
    last_seen: str | None = None
    last_change: str | None = None


@dataclass
class YenteSearchResult:
    """Paginert søk-respons fra /search-endepunktet."""

    items: list[YenteSearchEntity]
    total: int
    total_relation: str
    limit: int
    offset: int


class YenteClient:
    """Asynkron klient mot yente OpenSanctions-tjenesten.

    Bruker en delt httpx.AsyncClient for connection-pooling.
    Laget for injection via dependency i FastAPI, men kan ogsa brukes
    direkte i services som ikke har DI-kontekst.
    """

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.yente_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=_REQUEST_TIMEOUT,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ── Helsesjekk ───────────────────────────────────────────────────────────

    async def is_healthy(self) -> bool:
        """Returnerer True om yente svarer pa /healthz."""
        try:
            client = await self._get_client()
            resp = await client.get("/healthz")
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("yente_healthcheck_failed", error=str(exc))
            return False

    async def get_version(self) -> str | None:
        """Hent yente-versjon fra /healthz."""
        try:
            client = await self._get_client()
            resp = await client.get("/healthz")
            data = resp.json()
            return data.get("version")
        except Exception:
            return None

    # ── Datasett ─────────────────────────────────────────────────────────────

    async def list_datasets(self) -> list[YenteDataset]:
        """Hent alle konfigurerte datasett og deres status.

        Yente v5 bruker /catalog (ikke /datasets).
        """
        try:
            client = await self._get_client()
            resp = await client.get("/catalog")
            resp.raise_for_status()
            data = resp.json()
            datasets = []
            for ds in data.get("datasets", []):
                # v5 bruker index_status.status / index_current for status
                index_status = ds.get("index_status") or {}
                if ds.get("index_current"):
                    status = "loaded"
                elif index_status.get("status") == "indexing":
                    status = "indexing"
                elif index_status.get("error"):
                    status = "error"
                else:
                    status = "pending"
                datasets.append(
                    YenteDataset(
                        name=ds.get("name", ""),
                        title=ds.get("title"),
                        entity_count=ds.get("entity_count"),
                        last_updated=ds.get("updated_at") or ds.get("last_export"),
                        status=status,
                    )
                )
            return datasets
        except Exception as exc:
            logger.error("yente_list_datasets_failed", error=str(exc))
            return []

    async def trigger_update(self, *, token: str, sync: bool = False) -> httpx.Response:
        """Trigger /updatez for å laste ned og reindeksere datasett."""
        client = await self._get_client()
        return await client.post(
            "/updatez",
            params={"token": token, "sync": sync},
        )

    # ── Matching ──────────────────────────────────────────────────────────────

    async def match_entity(
        self,
        name: str,
        entity_type: str,
        country: str | None = None,
    ) -> list[YenteMatch]:
        """Match en enkelt entitet mot alle aktive datasett.

        Args:
            name:        Entitetens navn slik det star i fakturaen.
            entity_type: "person" | "company" | "vessel" | "aircraft"
            country:     ISO-3166 alfa-2 landkode (valgfritt, hever presisjon).

        Returns:
            Liste over treff sortert etter score (hoyest forst).
            Tom liste dersom yente ikke svarer eller ingen treff finnes.
        """
        schema = _FTM_SCHEMA.get(entity_type.lower(), "Company")
        props: dict[str, list[str]] = {"name": [name]}
        if country:
            props["country"] = [country]

        query_id = "q0"
        payload: dict[str, Any] = {
            "queries": {
                query_id: {
                    "schema": schema,
                    "properties": props,
                }
            }
        }

        try:
            client = await self._get_client()
            # Yente v4+: POST /match/{dataset} — "default" matcher mot alle
            # konfigurerte datasett aggregert. Tidligere versjon brukte POST /match
            # (uten datasett), men dette endepunktet finnes ikke lenger i v4+.
            resp = await client.post("/match/default", json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "yente_match_http_error",
                name=name,
                status=exc.response.status_code,
                error=str(exc),
            )
            return []
        except Exception as exc:
            logger.error("yente_match_failed", name=name, error=str(exc))
            return []

        results = data.get("responses", {}).get(query_id, {}).get("results", [])
        matches: list[YenteMatch] = []
        for hit in results:
            score = float(hit.get("score", 0.0))
            # Finn "listed_on" fra properties hvis tilgjengelig
            listed_on: date | None = None
            raw_props = hit.get("properties", {})
            for key in ("createdAt", "startDate", "incorporationDate"):
                val_list = raw_props.get(key, [])
                if val_list:
                    try:
                        listed_on = date.fromisoformat(val_list[0][:10])
                        break
                    except (ValueError, TypeError):
                        pass

            # Hent datasett fra hit
            for ds in hit.get("datasets", ["unknown"]):
                matches.append(
                    YenteMatch(
                        dataset=ds,
                        entity_id=hit.get("id"),
                        matched_name=hit.get("caption"),
                        score=score,
                        listed_on=listed_on,
                        raw=hit,
                    )
                )

        matches.sort(key=lambda m: m.score, reverse=True)
        logger.info(
            "yente_match_done",
            name=name,
            schema=schema,
            hits=len(matches),
        )
        return matches

    async def match_entities_batch(
        self,
        entities: list[dict[str, Any]],
        max_concurrent: int = 5,
    ) -> dict[str, list[YenteMatch] | None]:
        """Match flere entiteter parallelt.

        Args:
            entities: Liste av dicts med "id", "name", "entity_type", "country".
            max_concurrent: Maks parallelle HTTP-kall mot yente.

        Returns:
            Dict fra entity_id -> liste av YenteMatch, eller None om kallet feilet.
            Screening-servicen bruker None til a skille "ingen treff" fra "kall feilet".
        """
        sem = asyncio.Semaphore(max_concurrent)

        async def _match_one(
            entity: dict[str, Any],
        ) -> tuple[str, list[YenteMatch] | None]:
            async with sem:
                try:
                    hits = await self.match_entity(
                        name=entity["name"],
                        entity_type=entity.get("entity_type", "company"),
                        country=entity.get("country"),
                    )
                    return str(entity["id"]), hits
                except Exception as exc:
                    logger.error(
                        "yente_match_one_exception",
                        entity_id=str(entity["id"]),
                        error=str(exc),
                    )
                    return str(entity["id"]), None

        tasks = [_match_one(e) for e in entities]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: dict[str, list[YenteMatch] | None] = {}
        for entity, result in zip(entities, results, strict=False):
            eid = str(entity["id"])
            if isinstance(result, Exception):
                logger.error(
                    "yente_batch_gather_failed",
                    entity_id=eid,
                    error=str(result),
                )
                output[eid] = None
            else:
                _, hits = result
                output[eid] = hits

        return output

    async def search_entities(
        self,
        *,
        dataset: str = "default",
        query: str = "",
        schema: str = "Thing",
        topics: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
        fuzzy: bool = True,
        simple: bool = True,
    ) -> YenteSearchResult:
        """Søk etter entiteter via yente /search/{dataset}."""
        params: list[tuple[str, str | int | bool]] = [
            ("q", query),
            ("schema", schema),
            ("limit", limit),
            ("offset", offset),
            ("fuzzy", fuzzy),
            ("simple", simple),
        ]
        for topic in topics or []:
            params.append(("topics", topic))

        try:
            client = await self._get_client()
            resp = await client.get(f"/search/{dataset}", params=params)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.error(
                "yente_search_failed",
                dataset=dataset,
                query=query,
                schema=schema,
                error=str(exc),
            )
            return YenteSearchResult(
                items=[],
                total=0,
                total_relation="eq",
                limit=limit,
                offset=offset,
            )

        total_obj = data.get("total", {}) or {}
        results = data.get("results", []) or []
        items: list[YenteSearchEntity] = []
        for row in results:
            props = row.get("properties", {}) or {}
            countries = props.get("country", []) or []
            topics_value = props.get("topics", []) or []
            items.append(
                YenteSearchEntity(
                    id=row.get("id", ""),
                    caption=row.get("caption", ""),
                    schema=row.get("schema", "Thing"),
                    datasets=row.get("datasets", []) or [],
                    countries=[str(c) for c in countries if c is not None],
                    topics=[str(t) for t in topics_value if t is not None],
                    first_seen=row.get("first_seen"),
                    last_seen=row.get("last_seen"),
                    last_change=row.get("last_change"),
                )
            )

        return YenteSearchResult(
            items=items,
            total=int(total_obj.get("value", 0) or 0),
            total_relation=str(total_obj.get("relation", "eq") or "eq"),
            limit=int(data.get("limit", limit) or limit),
            offset=int(data.get("offset", offset) or offset),
        )


# ── Singleton for dependency injection ───────────────────────────────────────

_yente_client: YenteClient | None = None


def get_yente_client() -> YenteClient:
    """Returner en delt YenteClient-instans (singleton)."""
    global _yente_client
    if _yente_client is None:
        _yente_client = YenteClient()
    return _yente_client
