"""Permission resolver for trust zone RBAC with tree walking."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import col

from app.models.organization_members import OrganizationMember
from app.models.trust_zones import TrustZone
from app.models.zone_assignments import ZoneAssignment
from app.services.trust_zones import get_zone_ancestry

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

# Zone role → permission set
ZONE_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "executor": {"zone.read", "zone.execute", "task.create", "task.update"},
    "approver": {
        "zone.read",
        "proposal.review",
        "proposal.approve",
        "proposal.reject",
    },
    "evaluator": {"zone.read", "evaluation.create", "evaluation.submit"},
    "gardener": {
        "zone.read",
        "zone.write",
        "proposal.review",
        "reviewer.select",
    },
}

# Org role → fallback permission set
ORG_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": {"*"},
    "admin": {
        "zone.read",
        "zone.write",
        "zone.create",
        "zone.delete",
        "proposal.create",
        "proposal.approve",
        "proposal.reject",
        "proposal.review",
        "evaluation.create",
        "evaluation.submit",
        "escalation.trigger",
        "reviewer.select",
        "task.create",
        "task.update",
        "zone.execute",
    },
    "member": {"zone.read", "proposal.create", "escalation.trigger"},
}


def check_resource_scope(
    zone: TrustZone,
    context: dict[str, object],
) -> tuple[bool, str]:
    """Check resource scope constraints on a zone.

    Args:
        zone: The trust zone to check.
        context: Dict with optional keys: board_id, agent_type, budget_amount.

    Returns:
        (allowed, reason) — reason is empty on success, describes violation on failure.
    """
    scope = zone.resource_scope
    if scope is None:
        return True, ""

    # Check allowed_boards
    allowed_boards = scope.get("allowed_boards")
    if isinstance(allowed_boards, list) and len(allowed_boards) > 0:
        board_id = context.get("board_id")
        if board_id is not None and str(board_id) not in [str(b) for b in allowed_boards]:
            return False, f"Board {board_id} is not in zone's allowed_boards"

    # Check allowed_agent_types
    allowed_agent_types = scope.get("allowed_agent_types")
    if isinstance(allowed_agent_types, list) and len(allowed_agent_types) > 0:
        agent_type = context.get("agent_type")
        if agent_type is not None and str(agent_type) not in [str(a) for a in allowed_agent_types]:
            return False, f"Agent type '{agent_type}' is not in zone's allowed_agent_types"

    # Check budget_limit
    budget_limit = scope.get("budget_limit")
    if budget_limit is not None and isinstance(budget_limit, (int, float)):
        budget_amount = context.get("budget_amount")
        if budget_amount is not None and isinstance(budget_amount, (int, float)):
            if budget_amount > budget_limit:
                return False, f"Budget amount {budget_amount} exceeds zone limit of {budget_limit}"

    return True, ""


async def resolve_zone_permission(
    session: AsyncSession,
    *,
    member: OrganizationMember,
    zone: TrustZone,
    action: str,
    resource_context: dict[str, object] | None = None,
) -> bool:
    """Check if a member has permission for an action in a zone.

    Algorithm:
    1. Check zone constraints (hard rules)
    2. Walk zone tree child → parent, checking ZoneAssignment roles
    3. Fall back to OrganizationMember.role at root
    4. Owner gets wildcard '*'

    If resource_context is provided, also checks resource scope constraints.
    """
    # Step 1: Check zone constraints (hard rules)
    if not check_zone_constraints(zone=zone, action=action):
        return False

    # Step 1b: Check resource scope if context provided
    if resource_context is not None:
        allowed, _ = check_resource_scope(zone, resource_context)
        if not allowed:
            return False

    # Step 2: Walk zone ancestry checking assignments
    ancestry = await get_zone_ancestry(session, zone=zone)
    for ancestor in ancestry:
        assignments = (
            await ZoneAssignment.objects.filter_by(
                zone_id=ancestor.id,
                member_id=member.id,
            )
            .filter(col(ZoneAssignment.role).in_(list(ZONE_ROLE_PERMISSIONS.keys())))
            .all(session)
        )
        for assignment in assignments:
            perms = ZONE_ROLE_PERMISSIONS.get(assignment.role, set())
            if action in perms or "*" in perms:
                return True

    # Step 3: Fall back to org role
    org_perms = ORG_ROLE_PERMISSIONS.get(member.role, set())
    return action in org_perms or "*" in org_perms


def check_zone_constraints(
    *,
    zone: TrustZone,
    action: str,
) -> bool:
    """Check hard constraint rules on a zone. Returns False if action is blocked."""
    if zone.constraints is None:
        return True

    blocked = zone.constraints.get("blocked_actions")
    if isinstance(blocked, list) and action in blocked:
        return False

    allowed = zone.constraints.get("allowed_actions")
    if isinstance(allowed, list) and len(allowed) > 0:
        return action in allowed

    return True


async def get_effective_permissions(
    session: AsyncSession,
    *,
    member: OrganizationMember,
    zone: TrustZone,
) -> set[str]:
    """Compute the full set of effective permissions for a member in a zone."""
    permissions: set[str] = set()

    # Collect from zone assignments in ancestry
    ancestry = await get_zone_ancestry(session, zone=zone)
    for ancestor in ancestry:
        assignments = await ZoneAssignment.objects.filter_by(
            zone_id=ancestor.id,
            member_id=member.id,
        ).all(session)
        for assignment in assignments:
            perms = ZONE_ROLE_PERMISSIONS.get(assignment.role, set())
            permissions.update(perms)

    # Add org-level permissions
    org_perms = ORG_ROLE_PERMISSIONS.get(member.role, set())
    permissions.update(org_perms)

    # Filter by zone constraints
    if zone.constraints is not None:
        blocked = zone.constraints.get("blocked_actions")
        if isinstance(blocked, list):
            permissions -= set(blocked)

        allowed = zone.constraints.get("allowed_actions")
        if isinstance(allowed, list) and len(allowed) > 0 and "*" not in permissions:
            permissions &= set(allowed) | {"zone.read"}

    return permissions
