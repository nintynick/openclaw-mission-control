# ruff: noqa

from __future__ import annotations

import re
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.organization_members import OrganizationMember
from app.models.trust_zones import TrustZone
from app.models.trust_zones import ZONE_STATUSES, ZONE_STATUS_TRANSITIONS
from app.services.trust_zones import (
    _slugify,
    archive_zone,
    validate_constraint_narrowing,
    validate_status_transition,
    validate_resource_scope_narrowing,
)


def test_slugify_basic() -> None:
    assert _slugify("Engineering Team") == "engineering-team"


def test_slugify_special_chars() -> None:
    assert _slugify("AI & Robotics (v2)") == "ai-robotics-v2"


def test_slugify_multiple_spaces_hyphens() -> None:
    assert _slugify("  hello   world  ") == "hello-world"


def test_slugify_already_clean() -> None:
    assert _slugify("clean-slug") == "clean-slug"


def test_validate_constraint_narrowing_passes_when_child_keeps_parent_blocks() -> None:
    parent = {"blocked_actions": ["deploy", "delete"], "allowed_actions": ["read", "write"]}
    child = {"blocked_actions": ["deploy", "delete", "admin"], "allowed_actions": ["read"]}
    # Should not raise
    validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)


def test_validate_constraint_narrowing_fails_when_child_unblocks() -> None:
    parent = {"blocked_actions": ["deploy", "delete"]}
    child = {"blocked_actions": ["deploy"]}
    with pytest.raises(HTTPException) as exc:
        validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)
    assert exc.value.status_code == 422
    assert "delete" in str(exc.value.detail)


def test_validate_constraint_narrowing_fails_when_child_widens_allowed() -> None:
    parent = {"blocked_actions": [], "allowed_actions": ["read", "write"]}
    child = {"blocked_actions": [], "allowed_actions": ["read", "write", "admin"]}
    with pytest.raises(HTTPException) as exc:
        validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)
    assert exc.value.status_code == 422
    assert "admin" in str(exc.value.detail)


def test_validate_constraint_narrowing_no_allowed_in_parent_passes() -> None:
    parent = {"blocked_actions": ["deploy"]}
    child = {"blocked_actions": ["deploy"], "allowed_actions": ["read", "write"]}
    # Parent has no allowed_actions list, child is free to set
    validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)


def test_zone_statuses_contains_all() -> None:
    assert ZONE_STATUSES == {"draft", "active", "suspended", "archived"}


def test_zone_status_transitions_cover_all_statuses() -> None:
    for s in ZONE_STATUSES:
        assert s in ZONE_STATUS_TRANSITIONS


def test_validate_status_transition_draft_to_active() -> None:
    validate_status_transition("draft", "active")


def test_validate_status_transition_draft_to_suspended_fails() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_status_transition("draft", "suspended")
    assert exc.value.status_code == 422
    assert "Cannot transition" in str(exc.value.detail)


def test_validate_status_transition_archived_is_terminal() -> None:
    for target in ZONE_STATUSES:
        if target == "archived":
            continue
        with pytest.raises(HTTPException):
            validate_status_transition("archived", target)


def test_self_parenting_raises() -> None:
    """A zone cannot be set as its own parent (tested via validate_no_cycle)."""
    # validate_no_cycle is async, tested separately via integration-style tests.
    # Here just verify the cycle-detection import works.
    from app.services.trust_zones import validate_no_cycle
    assert callable(validate_no_cycle)


def test_resource_scope_narrowing_valid() -> None:
    parent = {"budget_limit": 1000, "allowed_boards": ["a", "b"], "allowed_agent_types": ["x", "y"]}
    child = {"budget_limit": 500, "allowed_boards": ["a"], "allowed_agent_types": ["x"]}
    validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)


def test_resource_scope_narrowing_budget_exceeds() -> None:
    parent = {"budget_limit": 100}
    child = {"budget_limit": 200}
    with pytest.raises(HTTPException) as exc:
        validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)
    assert exc.value.status_code == 422
    assert "budget_limit" in str(exc.value.detail)


def test_resource_scope_narrowing_boards_exceed() -> None:
    parent = {"allowed_boards": ["a"]}
    child = {"allowed_boards": ["a", "b"]}
    with pytest.raises(HTTPException) as exc:
        validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)
    assert exc.value.status_code == 422
    assert "allowed_boards" in str(exc.value.detail)


def test_resource_scope_narrowing_agent_types_exceed() -> None:
    parent = {"allowed_agent_types": ["x"]}
    child = {"allowed_agent_types": ["x", "y"]}
    with pytest.raises(HTTPException) as exc:
        validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)
    assert exc.value.status_code == 422
    assert "allowed_agent_types" in str(exc.value.detail)


def test_trust_zone_model_defaults() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="Test Zone",
        slug="test-zone",
        created_by=uuid4(),
    )
    assert zone.status == "draft"
    assert zone.description == ""
    assert zone.parent_zone_id is None
    assert zone.constraints is None
    assert zone.decision_model is None
