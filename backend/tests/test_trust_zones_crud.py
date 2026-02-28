# ruff: noqa

from __future__ import annotations

import re
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.organization_members import OrganizationMember
from app.models.trust_zones import TrustZone
from app.services.trust_zones import (
    _slugify,
    archive_zone,
    validate_constraint_narrowing,
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
