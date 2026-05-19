from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.security import ActorContext, get_actor_context, require_roles


def test_get_actor_context_valid() -> None:
    actor = get_actor_context(
        x_actor_role="ComPliance_Officer",
        x_actor_name="Ada Admin",
    )
    assert actor.role == "compliance_officer"
    assert actor.name == "Ada Admin"


def test_get_actor_context_missing_role_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        get_actor_context(x_actor_role="", x_actor_name="Anon")
    assert exc.value.status_code == 401


def test_get_actor_context_invalid_role_raises_403() -> None:
    with pytest.raises(HTTPException) as exc:
        get_actor_context(x_actor_role="superuser", x_actor_name="Anon")
    assert exc.value.status_code == 403


def test_require_roles_forbids_outside_role() -> None:
    dep = require_roles("admin", "compliance_officer")
    with pytest.raises(HTTPException) as exc:
        dep(actor=ActorContext(role="readonly", name="Read Only"))
    assert exc.value.status_code == 403


def test_require_roles_allows_inside_role() -> None:
    dep = require_roles("admin", "compliance_officer")
    actor = dep(actor=ActorContext(role="admin", name="Admin"))
    assert actor.role == "admin"


def test_require_roles_allows_c_level_when_admin_allowed() -> None:
    dep = require_roles("admin", "compliance_officer")
    actor = dep(actor=ActorContext(role="c_level", name="Sigurd Sjef"))
    assert actor.role == "c_level"
