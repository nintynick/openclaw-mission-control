"""Trust zone CRUD and hierarchy management service."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlmodel import col

from app.core.time import utcnow
from app.models.trust_zones import ZONE_STATUS_TRANSITIONS, ZONE_STATUSES, TrustZone

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.schemas.trust_zones import TrustZoneCreate, TrustZoneUpdate


def _slugify(name: str) -> str:
    """Generate a URL-safe slug from a zone name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")


# ---------------------------------------------------------------------------
# Gap 1 — Status transition validation
# ---------------------------------------------------------------------------


def validate_status_transition(current: str, target: str) -> None:
    """Check that *current* → *target* is an allowed zone status transition."""
    if target not in ZONE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid zone status: {target}",
        )
    allowed = ZONE_STATUS_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Cannot transition zone from '{current}' to '{target}'",
        )


# ---------------------------------------------------------------------------
# Gap 3 — Circular reference detection
# ---------------------------------------------------------------------------


async def validate_no_cycle(
    session: AsyncSession,
    *,
    zone_id: object,
    proposed_parent_id: object,
    organization_id: object,
) -> None:
    """Walk the parent chain from *proposed_parent_id* and raise 422 if *zone_id* is encountered."""
    if proposed_parent_id == zone_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A zone cannot be its own parent",
        )

    current_id = proposed_parent_id
    seen: set[object] = {zone_id}
    while current_id is not None:
        if current_id in seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Circular parent reference detected in zone hierarchy",
            )
        seen.add(current_id)
        parent = await TrustZone.objects.by_id(current_id).first(session)
        if parent is None or parent.organization_id != organization_id:
            break
        current_id = parent.parent_zone_id


# ---------------------------------------------------------------------------
# Gap 10 — Resource scope narrowing
# ---------------------------------------------------------------------------


def validate_resource_scope_narrowing(
    *,
    parent_scope: dict[str, object],
    child_scope: dict[str, object],
) -> None:
    """Validate that a child's resource_scope never exceeds the parent's."""
    parent_budget = parent_scope.get("budget_limit")
    child_budget = child_scope.get("budget_limit")
    if (
        isinstance(parent_budget, (int, float))
        and isinstance(child_budget, (int, float))
        and child_budget > parent_budget
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Child budget_limit ({child_budget}) exceeds "
                f"parent budget_limit ({parent_budget})"
            ),
        )

    parent_boards = parent_scope.get("allowed_boards")
    child_boards = child_scope.get("allowed_boards")
    if isinstance(parent_boards, list) and isinstance(child_boards, list):
        extra = set(child_boards) - set(parent_boards)
        if extra:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Child allowed_boards not in parent scope: "
                    f"{', '.join(sorted(str(b) for b in extra))}"
                ),
            )

    parent_agents = parent_scope.get("allowed_agent_types")
    child_agents = child_scope.get("allowed_agent_types")
    if isinstance(parent_agents, list) and isinstance(child_agents, list):
        extra = set(child_agents) - set(parent_agents)
        if extra:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Child allowed_agent_types not in parent scope: "
                    f"{', '.join(sorted(str(a) for a in extra))}"
                ),
            )

    # Generic: for any other matching numeric key, child cannot exceed parent
    known_keys = {"budget_limit", "allowed_boards", "allowed_agent_types"}
    for key in child_scope:
        if key in known_keys:
            continue
        parent_val = parent_scope.get(key)
        child_val = child_scope[key]
        if (
            isinstance(parent_val, (int, float))
            and isinstance(child_val, (int, float))
            and child_val > parent_val
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Child {key} ({child_val}) exceeds parent {key} ({parent_val})",
            )


# ---------------------------------------------------------------------------
# Zone CRUD
# ---------------------------------------------------------------------------


async def create_zone(
    session: AsyncSession,
    *,
    organization_id: UUID,
    created_by: UUID,
    payload: TrustZoneCreate,
) -> TrustZone:
    """Create a trust zone with slug generation and parent validation."""
    slug = payload.slug or _slugify(payload.name)

    # Validate slug uniqueness within org
    existing = await TrustZone.objects.filter_by(
        organization_id=organization_id,
        slug=slug,
    ).first(session)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Zone slug '{slug}' already exists in this organization",
        )

    # Validate parent zone exists and belongs to same org
    if payload.parent_zone_id is not None:
        parent = await TrustZone.objects.by_id(payload.parent_zone_id).first(session)
        if parent is None or parent.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Parent zone not found or belongs to different organization",
            )
        # Validate constraint narrowing
        if payload.constraints is not None and parent.constraints is not None:
            validate_constraint_narrowing(
                parent_constraints=parent.constraints,
                child_constraints=payload.constraints,
            )
        # Gap 10: Validate resource scope narrowing
        if payload.resource_scope is not None and parent.resource_scope is not None:
            validate_resource_scope_narrowing(
                parent_scope=parent.resource_scope,
                child_scope=payload.resource_scope,
            )

    now = utcnow()
    zone = TrustZone(
        organization_id=organization_id,
        parent_zone_id=payload.parent_zone_id,
        name=payload.name,
        slug=slug,
        description=payload.description,
        status=payload.status,
        created_by=created_by,
        responsibilities=payload.responsibilities,
        resource_scope=payload.resource_scope,
        agent_qualifications=payload.agent_qualifications,
        alignment_requirements=payload.alignment_requirements,
        incentive_model=payload.incentive_model,
        constraints=payload.constraints,
        decision_model=payload.decision_model,
        approval_policy=payload.approval_policy,
        escalation_policy=payload.escalation_policy,
        evaluation_criteria=payload.evaluation_criteria,
        created_at=now,
        updated_at=now,
    )
    session.add(zone)
    await session.commit()
    await session.refresh(zone)
    return zone


async def update_zone(
    session: AsyncSession,
    *,
    zone: TrustZone,
    payload: TrustZoneUpdate,
) -> TrustZone:
    """Update a trust zone with the provided fields.

    Validates status transitions, cycle detection, constraint narrowing,
    and resource scope narrowing against the effective parent.
    """
    updates = payload.model_dump(exclude_unset=True)

    # Gap 1: Validate status transition if status is being changed
    if "status" in updates and updates["status"] != zone.status:
        validate_status_transition(zone.status, updates["status"])

    # Gap 3: Validate no cycle if parent_zone_id is changing
    if "parent_zone_id" in updates and updates["parent_zone_id"] is not None:
        await validate_no_cycle(
            session,
            zone_id=zone.id,
            proposed_parent_id=updates["parent_zone_id"],
            organization_id=zone.organization_id,
        )

    # Resolve effective parent for narrowing checks
    effective_parent_id = updates.get("parent_zone_id", zone.parent_zone_id)
    parent: TrustZone | None = None
    if effective_parent_id is not None:
        parent = await TrustZone.objects.by_id(effective_parent_id).first(session)

    # Gap 15: Validate constraint narrowing against parent on update
    if "constraints" in updates and parent is not None and parent.constraints is not None:
        child_constraints = updates["constraints"]
        if child_constraints is not None:
            validate_constraint_narrowing(
                parent_constraints=parent.constraints,
                child_constraints=child_constraints,
            )

    # Gap 10: Validate resource scope narrowing against parent on update
    if "resource_scope" in updates and parent is not None and parent.resource_scope is not None:
        child_scope = updates["resource_scope"]
        if child_scope is not None:
            validate_resource_scope_narrowing(
                parent_scope=parent.resource_scope,
                child_scope=child_scope,
            )

    # When this zone's resource_scope is updated, validate existing children
    if "resource_scope" in updates and updates["resource_scope"] is not None:
        children = await get_zone_children(session, zone_id=zone.id)
        for child in children:
            if child.resource_scope is not None:
                validate_resource_scope_narrowing(
                    parent_scope=updates["resource_scope"],
                    child_scope=child.resource_scope,
                )

    for key, value in updates.items():
        setattr(zone, key, value)
    zone.updated_at = utcnow()
    session.add(zone)

    # Cascade status to children when archiving or suspending
    if "status" in updates and updates["status"] in ("archived", "suspended"):
        await cascade_status(session, zone=zone, target_status=updates["status"])

    await session.commit()
    await session.refresh(zone)
    return zone


async def get_zone_ancestry(
    session: AsyncSession,
    *,
    zone: TrustZone,
) -> list[TrustZone]:
    """Walk parent_zone_id chain to root. Returns [zone, parent, grandparent, ...]."""
    ancestry: list[TrustZone] = [zone]
    current = zone
    seen: set[object] = {zone.id}
    while current.parent_zone_id is not None:
        parent = await TrustZone.objects.by_id(current.parent_zone_id).first(session)
        if parent is None or parent.id in seen:
            break
        seen.add(parent.id)
        ancestry.append(parent)
        current = parent
    return ancestry


async def get_zone_children(
    session: AsyncSession,
    *,
    zone_id: UUID,
) -> list[TrustZone]:
    """Get direct children of a zone."""
    return await TrustZone.objects.filter_by(parent_zone_id=zone_id).all(session)


def validate_constraint_narrowing(
    *,
    parent_constraints: dict[str, object],
    child_constraints: dict[str, object],
) -> None:
    """Validate that child constraints only narrow (never widen) parent constraints.

    Blocked actions in the parent must remain blocked in the child.
    Allowed actions in the child must be a subset of the parent's allowed actions.
    """
    parent_blocked = set(parent_constraints.get("blocked_actions", []))  # type: ignore[arg-type]
    child_blocked = set(child_constraints.get("blocked_actions", []))  # type: ignore[arg-type]

    missing_blocks = parent_blocked - child_blocked
    if missing_blocks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Child zone cannot unblock parent-blocked actions: "
                f"{', '.join(sorted(missing_blocks))}"
            ),
        )

    parent_allowed = parent_constraints.get("allowed_actions")
    child_allowed = child_constraints.get("allowed_actions")
    if isinstance(parent_allowed, list) and isinstance(child_allowed, list):
        parent_set = set(parent_allowed)
        child_set = set(child_allowed)
        extra = child_set - parent_set
        if extra:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Child zone cannot allow actions not allowed by parent: "
                    f"{', '.join(sorted(extra))}"
                ),
            )


# ---------------------------------------------------------------------------
# Gap 2 — Cascade status on archive / suspend
# ---------------------------------------------------------------------------


async def cascade_status(
    session: AsyncSession,
    *,
    zone: TrustZone,
    target_status: str,
) -> list[TrustZone]:
    """Recursively transition children to *target_status*, skipping invalid transitions."""
    affected: list[TrustZone] = []
    children = await get_zone_children(session, zone_id=zone.id)
    now = utcnow()
    for child in children:
        allowed = ZONE_STATUS_TRANSITIONS.get(child.status, set())
        if target_status in allowed:
            child.status = target_status
            child.updated_at = now
            session.add(child)
            affected.append(child)
            # Recurse into grandchildren
            affected.extend(
                await cascade_status(session, zone=child, target_status=target_status)
            )
    return affected


async def archive_zone(
    session: AsyncSession,
    *,
    zone: TrustZone,
) -> TrustZone:
    """Soft-delete a zone by setting status to archived, cascading to children."""
    zone.status = "archived"
    zone.updated_at = utcnow()
    session.add(zone)
    # Gap 2: Cascade archive to children
    await cascade_status(session, zone=zone, target_status="archived")
    await session.commit()
    await session.refresh(zone)
    return zone


async def suspend_zone(
    session: AsyncSession,
    *,
    zone: TrustZone,
) -> TrustZone:
    """Suspend a zone, cascading to children."""
    validate_status_transition(zone.status, "suspended")
    zone.status = "suspended"
    zone.updated_at = utcnow()
    session.add(zone)
    # Gap 2: Cascade suspend to children
    await cascade_status(session, zone=zone, target_status="suspended")
    await session.commit()
    await session.refresh(zone)
    return zone
