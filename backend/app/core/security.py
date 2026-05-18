"""Enkel server-side rollevalidering for dev/pilot.

Bruker headers fra frontend:
  - X-Actor-Role
  - X-Actor-Name

Dette er ikke en erstatning for JWT, men gir faktisk backend-enforcement i dag.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import Depends, Header, HTTPException, status

VALID_ROLES = {"admin", "compliance_officer", "controller", "readonly"}


@dataclass(frozen=True)
class ActorContext:
    role: str
    name: str


def get_actor_context(
    x_actor_role: str | None = Header(default=None, alias="X-Actor-Role"),
    x_actor_name: str | None = Header(default=None, alias="X-Actor-Name"),
) -> ActorContext:
    role = (x_actor_role or "").strip().lower()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mangler autentiseringsheader: X-Actor-Role",
        )
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Ugyldig rolle: {role!r}",
        )

    name = (x_actor_name or "").strip() or role
    return ActorContext(role=role, name=name)


def require_roles(*allowed_roles: str) -> Callable[[ActorContext], ActorContext]:
    allowed = {r.strip().lower() for r in allowed_roles if r and r.strip()}

    if not allowed:
        raise ValueError("require_roles() må få minst én rolle.")

    def _dependency(
        actor: ActorContext = Depends(get_actor_context),
    ) -> ActorContext:
        if actor.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Tilgang nektet for rolle "
                    f"{actor.role!r}. Krever en av: {sorted(allowed)}"
                ),
            )
        return actor

    return _dependency

