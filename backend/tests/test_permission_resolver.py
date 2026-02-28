# ruff: noqa

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.models.organization_members import OrganizationMember
from app.models.trust_zones import TrustZone
from app.models.zone_assignments import ZoneAssignment
from app.services.permission_resolver import (
    ORG_ROLE_PERMISSIONS,
    ZONE_ROLE_PERMISSIONS,
    check_zone_constraints,
    get_effective_permissions,
    resolve_zone_permission,
)


@dataclass
class _FakeExecResult:
    first_value: Any = None
    all_values: list[Any] | None = None

    def first(self) -> Any:
        return self.first_value

    def __iter__(self):
        return iter(self.all_values or [])


@dataclass
class _FakeSession:
    exec_results: list[Any] = field(default_factory=list)

    async def exec(self, _statement: Any) -> Any:
        if not self.exec_results:
            return _FakeExecResult()
        return self.exec_results.pop(0)

    def add(self, _value: Any) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def refresh(self, _value: Any) -> None:
        pass


def test_check_zone_constraints_no_constraints() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="z",
        slug="z",
        created_by=uuid4(),
        constraints=None,
    )
    assert check_zone_constraints(zone=zone, action="anything") is True


def test_check_zone_constraints_blocked_action() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="z",
        slug="z",
        created_by=uuid4(),
        constraints={"blocked_actions": ["deploy", "delete"]},
    )
    assert check_zone_constraints(zone=zone, action="deploy") is False
    assert check_zone_constraints(zone=zone, action="read") is True


def test_check_zone_constraints_allowed_action_whitelist() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="z",
        slug="z",
        created_by=uuid4(),
        constraints={"blocked_actions": [], "allowed_actions": ["read", "write"]},
    )
    assert check_zone_constraints(zone=zone, action="read") is True
    assert check_zone_constraints(zone=zone, action="deploy") is False


def test_org_role_owner_wildcard() -> None:
    assert "*" in ORG_ROLE_PERMISSIONS["owner"]


def test_org_role_member_has_read() -> None:
    assert "zone.read" in ORG_ROLE_PERMISSIONS["member"]
    assert "zone.write" not in ORG_ROLE_PERMISSIONS["member"]


def test_zone_role_executor_permissions() -> None:
    perms = ZONE_ROLE_PERMISSIONS["executor"]
    assert "zone.execute" in perms
    assert "task.create" in perms
    assert "proposal.approve" not in perms


def test_zone_role_approver_permissions() -> None:
    perms = ZONE_ROLE_PERMISSIONS["approver"]
    assert "proposal.approve" in perms
    assert "proposal.reject" in perms
    assert "zone.execute" not in perms


def test_zone_role_gardener_permissions() -> None:
    perms = ZONE_ROLE_PERMISSIONS["gardener"]
    assert "zone.write" in perms
    assert "reviewer.select" in perms


@pytest.mark.asyncio
async def test_resolve_zone_permission_owner_always_allowed() -> None:
    org_id = uuid4()
    member = OrganizationMember(
        id=uuid4(),
        organization_id=org_id,
        user_id=uuid4(),
        role="owner",
    )
    zone = TrustZone(
        id=uuid4(),
        organization_id=org_id,
        parent_zone_id=None,
        name="root",
        slug="root",
        created_by=uuid4(),
    )

    # No zone assignments, but owner has wildcard
    session = _FakeSession(exec_results=[
        # get_zone_ancestry walks: first zone has no parent, so only 1 assignment lookup
        _FakeExecResult(all_values=[]),  # assignments for zone
    ])
    assert await resolve_zone_permission(
        session, member=member, zone=zone, action="anything"
    ) is True


@pytest.mark.asyncio
async def test_resolve_zone_permission_member_denied_write() -> None:
    org_id = uuid4()
    member = OrganizationMember(
        id=uuid4(),
        organization_id=org_id,
        user_id=uuid4(),
        role="member",
    )
    zone = TrustZone(
        id=uuid4(),
        organization_id=org_id,
        parent_zone_id=None,
        name="root",
        slug="root",
        created_by=uuid4(),
    )

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[]),  # no assignments
    ])
    assert await resolve_zone_permission(
        session, member=member, zone=zone, action="zone.write"
    ) is False


@pytest.mark.asyncio
async def test_resolve_zone_permission_executor_can_execute() -> None:
    org_id = uuid4()
    member_id = uuid4()
    zone_id = uuid4()
    member = OrganizationMember(
        id=member_id,
        organization_id=org_id,
        user_id=uuid4(),
        role="member",
    )
    zone = TrustZone(
        id=zone_id,
        organization_id=org_id,
        parent_zone_id=None,
        name="exec-zone",
        slug="exec-zone",
        created_by=uuid4(),
    )
    assignment = ZoneAssignment(
        zone_id=zone_id,
        member_id=member_id,
        role="executor",
        assigned_by=uuid4(),
    )

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[assignment]),  # assignments in zone
    ])
    assert await resolve_zone_permission(
        session, member=member, zone=zone, action="zone.execute"
    ) is True


@pytest.mark.asyncio
async def test_resolve_zone_permission_blocked_by_constraint() -> None:
    org_id = uuid4()
    member = OrganizationMember(
        id=uuid4(),
        organization_id=org_id,
        user_id=uuid4(),
        role="owner",
    )
    zone = TrustZone(
        id=uuid4(),
        organization_id=org_id,
        parent_zone_id=None,
        name="blocked",
        slug="blocked",
        created_by=uuid4(),
        constraints={"blocked_actions": ["zone.execute"]},
    )

    session = _FakeSession(exec_results=[])
    assert await resolve_zone_permission(
        session, member=member, zone=zone, action="zone.execute"
    ) is False
