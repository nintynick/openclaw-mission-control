# ruff: noqa

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.services.trust_zones import validate_constraint_narrowing, validate_resource_scope_narrowing


def test_child_can_add_more_blocks() -> None:
    parent = {"blocked_actions": ["deploy"]}
    child = {"blocked_actions": ["deploy", "delete"]}
    validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)


def test_child_cannot_remove_blocks() -> None:
    parent = {"blocked_actions": ["deploy", "delete"]}
    child = {"blocked_actions": []}
    with pytest.raises(HTTPException) as exc:
        validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)
    assert exc.value.status_code == 422


def test_child_allowed_must_be_subset_of_parent() -> None:
    parent = {"blocked_actions": [], "allowed_actions": ["read", "write"]}
    child = {"blocked_actions": [], "allowed_actions": ["read"]}
    validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)


def test_child_cannot_widen_allowed() -> None:
    parent = {"blocked_actions": [], "allowed_actions": ["read"]}
    child = {"blocked_actions": [], "allowed_actions": ["read", "write"]}
    with pytest.raises(HTTPException) as exc:
        validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)
    assert exc.value.status_code == 422
    assert "write" in str(exc.value.detail)


def test_no_parent_allowed_actions_allows_anything() -> None:
    parent = {"blocked_actions": []}
    child = {"blocked_actions": [], "allowed_actions": ["anything"]}
    validate_constraint_narrowing(parent_constraints=parent, child_constraints=child)


def test_empty_constraints_pass() -> None:
    validate_constraint_narrowing(parent_constraints={}, child_constraints={})


# --- Resource scope narrowing (Gap 10) ---


def test_resource_scope_equal_budget_passes() -> None:
    parent = {"budget_limit": 500}
    child = {"budget_limit": 500}
    validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)


def test_resource_scope_no_budget_in_parent_passes() -> None:
    parent = {}
    child = {"budget_limit": 999}
    validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)


def test_resource_scope_child_budget_over_parent_fails() -> None:
    from fastapi import HTTPException
    parent = {"budget_limit": 100}
    child = {"budget_limit": 101}
    with pytest.raises(HTTPException) as exc:
        validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)
    assert exc.value.status_code == 422


def test_resource_scope_boards_subset_passes() -> None:
    parent = {"allowed_boards": ["a", "b", "c"]}
    child = {"allowed_boards": ["a", "c"]}
    validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)


def test_resource_scope_boards_superset_fails() -> None:
    from fastapi import HTTPException
    parent = {"allowed_boards": ["a"]}
    child = {"allowed_boards": ["a", "z"]}
    with pytest.raises(HTTPException):
        validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)


def test_resource_scope_agent_types_subset_passes() -> None:
    parent = {"allowed_agent_types": ["x", "y"]}
    child = {"allowed_agent_types": ["y"]}
    validate_resource_scope_narrowing(parent_scope=parent, child_scope=child)
