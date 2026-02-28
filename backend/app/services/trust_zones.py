"""Trust zone CRUD and hierarchy management service."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlmodel import col

from app.core.time import utcnow
from app.models.trust_zones import TrustZone

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
    """Update a trust zone with the provided fields."""
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(zone, key, value)
    zone.updated_at = utcnow()
    session.add(zone)
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


async def archive_zone(
    session: AsyncSession,
    *,
    zone: TrustZone,
) -> TrustZone:
    """Soft-delete a zone by setting status to archived."""
    zone.status = "archived"
    zone.updated_at = utcnow()
    session.add(zone)
    await session.commit()
    await session.refresh(zone)
    return zone
