"""Trust zone management endpoints, zone assignments, and zone hierarchy."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col

from app.api.deps import require_org_admin, require_org_member
from app.core.auth import get_auth_context
from app.db.session import get_session
from app.models.organization_members import OrganizationMember
from app.models.trust_zones import TrustZone
from app.models.zone_assignments import ZoneAssignment
from app.schemas.common import OkResponse
from app.schemas.trust_zones import (
    TrustZoneCreate,
    TrustZoneRead,
    TrustZoneUpdate,
    ZoneAssignmentCreate,
    ZoneAssignmentRead,
)
from app.services.audit import record_audit
from app.services.organizations import OrganizationContext, is_org_admin
from app.services.permission_resolver import resolve_zone_permission
from app.services.trust_zones import (
    archive_zone,
    create_zone,
    get_zone_ancestry,
    get_zone_children,
    update_zone,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.core.auth import AuthContext

router = APIRouter(prefix="/organizations/me/zones", tags=["trust-zones"])
SESSION_DEP = Depends(get_session)
AUTH_DEP = Depends(get_auth_context)
ORG_MEMBER_DEP = Depends(require_org_member)
ORG_ADMIN_DEP = Depends(require_org_admin)


async def _get_zone_or_404(
    session: AsyncSession,
    *,
    zone_id: UUID,
    organization_id: UUID,
) -> TrustZone:
    """Load a zone and verify org ownership or raise 404."""
    zone = await TrustZone.objects.by_id(zone_id).first(session)
    if zone is None or zone.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return zone


@router.post("", response_model=TrustZoneRead)
async def create_trust_zone(
    payload: TrustZoneCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> TrustZoneRead:
    """Create a trust zone in the active organization."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    if not is_org_admin(ctx.member):
        # Non-admins can only create child zones where they have zone.create perm
        if payload.parent_zone_id is not None:
            parent = await TrustZone.objects.by_id(payload.parent_zone_id).first(
                session
            )
            if parent is not None:
                has_perm = await resolve_zone_permission(
                    session,
                    member=ctx.member,
                    zone=parent,
                    action="zone.create",
                )
                if not has_perm:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    zone = await create_zone(
        session,
        organization_id=ctx.organization.id,
        created_by=auth.user.id,
        payload=payload,
    )
    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="zone.create",
        zone_id=zone.id,
        target_type="trust_zone",
        target_id=zone.id,
    )
    return TrustZoneRead.model_validate(zone, from_attributes=True)


@router.get("", response_model=list[TrustZoneRead])
async def list_trust_zones(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
    parent_zone_id: UUID | None = None,
    zone_status: str | None = None,
) -> list[TrustZoneRead]:
    """List trust zones in the active organization."""
    query = TrustZone.objects.filter_by(organization_id=ctx.organization.id)
    if parent_zone_id is not None:
        query = query.filter_by(parent_zone_id=parent_zone_id)
    if zone_status is not None:
        query = query.filter(col(TrustZone.status) == zone_status)
    zones = await query.order_by(col(TrustZone.created_at).asc()).all(session)
    return [TrustZoneRead.model_validate(z, from_attributes=True) for z in zones]


@router.get("/{zone_id}", response_model=TrustZoneRead)
async def get_trust_zone(
    zone_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> TrustZoneRead:
    """Get a trust zone by id."""
    zone = await _get_zone_or_404(
        session, zone_id=zone_id, organization_id=ctx.organization.id
    )
    return TrustZoneRead.model_validate(zone, from_attributes=True)


@router.patch("/{zone_id}", response_model=TrustZoneRead)
async def update_trust_zone(
    zone_id: UUID,
    payload: TrustZoneUpdate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> TrustZoneRead:
    """Update a trust zone."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    zone = await _get_zone_or_404(
        session, zone_id=zone_id, organization_id=ctx.organization.id
    )
    if not is_org_admin(ctx.member):
        has_perm = await resolve_zone_permission(
            session, member=ctx.member, zone=zone, action="zone.write"
        )
        if not has_perm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    zone = await update_zone(session, zone=zone, payload=payload)
    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="zone.update",
        zone_id=zone.id,
        target_type="trust_zone",
        target_id=zone.id,
    )
    return TrustZoneRead.model_validate(zone, from_attributes=True)


@router.delete("/{zone_id}", response_model=TrustZoneRead)
async def delete_trust_zone(
    zone_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_ADMIN_DEP,
) -> TrustZoneRead:
    """Archive (soft delete) a trust zone."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    zone = await _get_zone_or_404(
        session, zone_id=zone_id, organization_id=ctx.organization.id
    )
    zone = await archive_zone(session, zone=zone)
    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="zone.archive",
        zone_id=zone.id,
        target_type="trust_zone",
        target_id=zone.id,
    )
    return TrustZoneRead.model_validate(zone, from_attributes=True)


@router.get("/{zone_id}/children", response_model=list[TrustZoneRead])
async def list_zone_children(
    zone_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> list[TrustZoneRead]:
    """List direct children of a trust zone."""
    await _get_zone_or_404(
        session, zone_id=zone_id, organization_id=ctx.organization.id
    )
    children = await get_zone_children(session, zone_id=zone_id)
    return [TrustZoneRead.model_validate(z, from_attributes=True) for z in children]


@router.get("/{zone_id}/ancestry", response_model=list[TrustZoneRead])
async def list_zone_ancestry(
    zone_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> list[TrustZoneRead]:
    """Get ancestry chain from zone to root."""
    zone = await _get_zone_or_404(
        session, zone_id=zone_id, organization_id=ctx.organization.id
    )
    ancestry = await get_zone_ancestry(session, zone=zone)
    return [TrustZoneRead.model_validate(z, from_attributes=True) for z in ancestry]


@router.post("/{zone_id}/assignments", response_model=ZoneAssignmentRead)
async def create_zone_assignment(
    zone_id: UUID,
    payload: ZoneAssignmentCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> ZoneAssignmentRead:
    """Assign a member to a role in a trust zone."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    zone = await _get_zone_or_404(
        session, zone_id=zone_id, organization_id=ctx.organization.id
    )
    if not is_org_admin(ctx.member):
        has_perm = await resolve_zone_permission(
            session, member=ctx.member, zone=zone, action="zone.write"
        )
        if not has_perm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    # Validate role
    valid_roles = {"executor", "approver", "evaluator", "gardener"}
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid role. Must be one of: {', '.join(sorted(valid_roles))}",
        )

    # Validate member belongs to same org
    member = await OrganizationMember.objects.by_id(payload.member_id).first(session)
    if member is None or member.organization_id != ctx.organization.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Member not found in organization",
        )

    # Check for existing assignment
    existing = await ZoneAssignment.objects.filter_by(
        zone_id=zone_id,
        member_id=payload.member_id,
        role=payload.role,
    ).first(session)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment already exists",
        )

    from app.core.time import utcnow

    now = utcnow()
    assignment = ZoneAssignment(
        zone_id=zone_id,
        member_id=payload.member_id,
        role=payload.role,
        assigned_by=auth.user.id,
        created_at=now,
        updated_at=now,
    )
    session.add(assignment)
    await session.commit()
    await session.refresh(assignment)

    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="zone.assign",
        zone_id=zone_id,
        target_type="zone_assignment",
        target_id=assignment.id,
        payload={"member_id": str(payload.member_id), "role": payload.role},
    )
    return ZoneAssignmentRead.model_validate(assignment, from_attributes=True)


@router.get("/{zone_id}/assignments", response_model=list[ZoneAssignmentRead])
async def list_zone_assignments(
    zone_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> list[ZoneAssignmentRead]:
    """List all assignments for a trust zone."""
    await _get_zone_or_404(
        session, zone_id=zone_id, organization_id=ctx.organization.id
    )
    assignments = await ZoneAssignment.objects.filter_by(zone_id=zone_id).all(session)
    return [
        ZoneAssignmentRead.model_validate(a, from_attributes=True) for a in assignments
    ]


@router.delete("/{zone_id}/assignments/{assignment_id}", response_model=OkResponse)
async def remove_zone_assignment(
    zone_id: UUID,
    assignment_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> OkResponse:
    """Remove a zone assignment."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    zone = await _get_zone_or_404(
        session, zone_id=zone_id, organization_id=ctx.organization.id
    )
    if not is_org_admin(ctx.member):
        has_perm = await resolve_zone_permission(
            session, member=ctx.member, zone=zone, action="zone.write"
        )
        if not has_perm:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    assignment = await ZoneAssignment.objects.by_id(assignment_id).first(session)
    if assignment is None or assignment.zone_id != zone_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    from app.db import crud

    await crud.delete(session, assignment)

    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="zone.unassign",
        zone_id=zone_id,
        target_type="zone_assignment",
        target_id=assignment_id,
    )
    return OkResponse()
