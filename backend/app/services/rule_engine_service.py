"""Regelmotor — evaluerer YAML-regler mot en invoice.

Arkitektur:
  1. YAML parses til en ConditionNode-tre (rekursivt AND/OR/NOT)
  2. InvoiceContext flater ut alle relevante felt fra en Invoice-ORM-rad
  3. evaluate(node, context) traverserer treet og returnerer True/False
  4. Hvert treff logger via audit_service

YAML-format:
  name: <str>
  description: <str>
  severity: green|yellow|red
  conditions:
    operator: AND|OR|NOT
    rules:
      - field: <dot.path>
        op: eq|neq|in|not_in|contains|not_contains|regex|gt|gte|lt|lte|exists
        value: <scalar|list>
      - operator: AND|OR|NOT   # nøsting
        rules: [...]

Eksempel-felt (dot.path):
  destination_country, compliance_score, total_amount, currency,
  entities.name, entities.country, entities.role, entities.email,
  lines.hs_code, lines.eccn, lines.description
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.invoice import Invoice
from app.models.rule import Rule, RuleVersion, RuleSeverity
from app.services import audit_service

logger = get_logger(__name__)

# ── InvoiceContext ─────────────────────────────────────────────────────────────


@dataclass
class InvoiceContext:
    """Flattenert representasjon av en Invoice for regelsjekk."""

    invoice_id: uuid.UUID
    destination_country: str | None
    compliance_score: str | None
    currency: str | None
    total_amount: float | None
    invoice_number: str | None
    direction: str | None
    status: str | None
    incoterms: str | None
    # lister av dicts
    entities: list[dict[str, Any]] = field(default_factory=list)
    lines: list[dict[str, Any]] = field(default_factory=list)


def build_context(
    invoice: Invoice,
    entities: list | None = None,
    lines: list | None = None,
) -> InvoiceContext:
    """Bygg InvoiceContext.

    ``entities`` og ``lines`` kan oppgis eksplisitt for å unngå lazy-loading
    i async SQLAlchemy. Hvis None, brukes invoice.entities / invoice.lines
    (krever at disse er eagerly loaded i ORM-sessionen).
    """
    ctx = InvoiceContext(
        invoice_id=invoice.id,
        destination_country=invoice.destination_country,
        compliance_score=invoice.compliance_score.value if invoice.compliance_score else None,
        currency=invoice.currency,
        total_amount=float(invoice.total_amount) if invoice.total_amount else None,
        invoice_number=invoice.invoice_number,
        direction=invoice.direction.value if invoice.direction else None,
        status=invoice.status.value if invoice.status else None,
        incoterms=invoice.incoterms,
    )
    entity_list = entities if entities is not None else list(invoice.entities)
    line_list = lines if lines is not None else list(invoice.lines)

    for e in entity_list:
        ctx.entities.append(
            {
                "name": e.name,
                "country": e.country,
                "role": e.role.value if e.role else None,
                "email": e.email,
                "entity_type": e.entity_type.value if e.entity_type else None,
            }
        )
    for ln in line_list:
        ctx.lines.append(
            {
                "description": ln.description,
                "hs_code": ln.hs_code,
                "eccn": ln.eccn,
                "product_code": ln.product_code,
            }
        )
    return ctx


# ── Condition-evaluering ──────────────────────────────────────────────────────


def _resolve_field(ctx: InvoiceContext, field_path: str) -> list[Any]:
    """Hent verdier for et felt (kan være liste for entities/lines).

    Returnerer alltid en liste slik at evalueringen er uniform.
    """
    parts = field_path.split(".", 1)
    root = parts[0]
    sub = parts[1] if len(parts) > 1 else None

    if root == "entities":
        items = ctx.entities
    elif root == "lines":
        items = ctx.lines
    else:
        # Enkelt toppnivå-felt
        val = getattr(ctx, root, None)
        return [val] if val is not None else []

    if sub is None:
        return [str(item) for item in items]
    return [item.get(sub) for item in items if item.get(sub) is not None]


def _coerce(val: Any, target: Any) -> Any:
    """Prøv å sammenligne med riktig type (numeric-safe)."""
    if isinstance(target, (int, float)):
        try:
            return type(target)(val)
        except (TypeError, ValueError):
            return val
    return str(val) if val is not None else val


def _match_op(values: list[Any], op: str, threshold: Any) -> bool:
    """Returner True hvis minst én verdi i listen oppfyller betingelsen."""
    if not values and op == "exists":
        return False
    if not values:
        return False

    for val in values:
        coerced = _coerce(val, threshold)
        match op:
            case "eq":
                if coerced == threshold:
                    return True
            case "neq":
                if coerced != threshold:
                    return True
            case "in":
                if isinstance(threshold, list) and coerced in threshold:
                    return True
            case "not_in":
                if isinstance(threshold, list) and coerced not in threshold:
                    return True
            case "contains":
                if threshold and threshold.lower() in str(val).lower():
                    return True
            case "not_contains":
                if threshold and threshold.lower() not in str(val).lower():
                    return True
            case "regex":
                if re.search(threshold, str(val), re.IGNORECASE):
                    return True
            case "gt":
                if coerced > threshold:
                    return True
            case "gte":
                if coerced >= threshold:
                    return True
            case "lt":
                if coerced < threshold:
                    return True
            case "lte":
                if coerced <= threshold:
                    return True
            case "exists":
                return True
    return False


def _evaluate_node(node: dict[str, Any], ctx: InvoiceContext) -> bool:
    """Rekursivt evaluer en betingelses-node."""
    if "operator" in node:
        op = node["operator"].upper()
        children = node.get("rules", [])
        if op == "AND":
            return all(_evaluate_node(c, ctx) for c in children)
        elif op == "OR":
            return any(_evaluate_node(c, ctx) for c in children)
        elif op == "NOT":
            return not any(_evaluate_node(c, ctx) for c in children)
        else:
            raise ValueError(f"Ukjent operator: {op!r}")
    else:
        # Leaf node
        fld = node["field"]
        op = node["op"]
        threshold = node.get("value")
        values = _resolve_field(ctx, fld)
        return _match_op(values, op, threshold)


# ── YAML-parsing ───────────────────────────────────────────────────────────────


def parse_rule_yaml(yaml_text: str) -> dict[str, Any]:
    """Parse YAML-tekst og valider minimumsstruktur."""
    data = yaml.safe_load(yaml_text)
    if not isinstance(data, dict):
        raise ValueError("YAML-regelen må være et mapping-objekt")
    if "name" not in data:
        raise ValueError("Mangler påkrevd felt: name")
    if "conditions" not in data:
        raise ValueError("Mangler påkrevd felt: conditions")
    return data


# ── Regelsjekk mot invoice ────────────────────────────────────────────────────


@dataclass
class RuleResult:
    rule_id: uuid.UUID
    rule_name: str
    version: int
    severity: str
    triggered: bool
    description: str | None = None


async def evaluate_invoice(
    session: AsyncSession,
    invoice: Invoice,
    *,
    entities: list | None = None,
    lines: list | None = None,
    write_audit: bool = True,
) -> list[RuleResult]:
    """Evaluer alle aktive regler mot invoice.

    Returnerer en liste med resultater for alle regler.
    Innslag logges i audit-loggen for regler som trigges.

    ``entities`` / ``lines``: pre-loadede lister for å unngå async lazy-load-feil.
    """
    # Hent aktive regler med aktiv versjon
    stmt = (
        select(Rule)
        .where(Rule.is_active == True)  # noqa: E712
        .options(selectinload(Rule.versions))
    )
    rules = list((await session.execute(stmt)).scalars().all())

    ctx = build_context(invoice, entities=entities, lines=lines)
    results: list[RuleResult] = []

    for rule in rules:
        # Finn aktiv versjon
        active_ver = next(
            (v for v in rule.versions if v.version == rule.active_version), None
        )
        if active_ver is None or not active_ver.rule_definition:
            continue

        try:
            triggered = _evaluate_node(
                active_ver.rule_definition.get("conditions", {}), ctx
            )
        except Exception as exc:
            logger.warning("rule_eval_error", rule=rule.name, error=str(exc))
            triggered = False

        results.append(
            RuleResult(
                rule_id=rule.id,
                rule_name=rule.name,
                version=rule.active_version,
                severity=rule.severity.value,
                triggered=triggered,
                description=rule.description,
            )
        )

        if triggered and write_audit:
            await audit_service.log(
                session,
                action="rule.triggered",
                invoice_id=invoice.id,
                details={
                    "rule_id": str(rule.id),
                    "rule_name": rule.name,
                    "version": rule.active_version,
                    "severity": rule.severity.value,
                },
            )

    return results


# ── CRUD-hjelpere ─────────────────────────────────────────────────────────────


async def create_rule(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    severity: str,
    yaml_text: str,
    created_by: str = "system",
    comment: str | None = None,
) -> Rule:
    """Opprett ny regel med versjon 1."""
    definition = parse_rule_yaml(yaml_text)
    rule = Rule(
        name=name,
        description=description,
        severity=RuleSeverity(severity),
        active_version=1,
    )
    session.add(rule)
    await session.flush()  # gir rule.id

    version = RuleVersion(
        rule_id=rule.id,
        version=1,
        rule_yaml=yaml_text,
        rule_definition=definition,
        created_by=created_by,
        created_at=datetime.now(tz=timezone.utc),
        comment=comment,
    )
    session.add(version)
    await session.flush()
    return rule


async def update_rule(
    session: AsyncSession,
    rule_id: uuid.UUID,
    *,
    yaml_text: str,
    created_by: str = "system",
    comment: str | None = None,
    name: str | None = None,
    description: str | None = None,
    severity: str | None = None,
) -> Rule:
    """Legg til ny versjon og bump active_version."""
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.versions))
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        from app.core.errors import NotFoundError
        raise NotFoundError(f"Regel {rule_id} finnes ikke")

    definition = parse_rule_yaml(yaml_text)
    new_ver_num = rule.active_version + 1

    if name is not None:
        rule.name = name
    if description is not None:
        rule.description = description
    if severity is not None:
        rule.severity = RuleSeverity(severity)
    rule.active_version = new_ver_num

    version = RuleVersion(
        rule_id=rule.id,
        version=new_ver_num,
        rule_yaml=yaml_text,
        rule_definition=definition,
        created_by=created_by,
        created_at=datetime.now(tz=timezone.utc),
        comment=comment,
    )
    session.add(version)
    await session.flush()
    return rule


async def list_rules(session: AsyncSession) -> list[Rule]:
    result = await session.execute(
        select(Rule).options(selectinload(Rule.versions)).order_by(Rule.name)
    )
    return list(result.scalars().all())


async def get_rule(session: AsyncSession, rule_id: uuid.UUID) -> Rule:
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id).options(selectinload(Rule.versions))
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        from app.core.errors import NotFoundError
        raise NotFoundError(f"Regel {rule_id} finnes ikke")
    return rule
