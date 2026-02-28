"""Escalation management endpoints for action and governance escalation workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col

from app.api.deps import require_org_member
from app.core.auth import get_auth_context
from app.db.session import get_session
from app.models.escalations import Escalation, EscalationCosigner
from app.models.proposals import Proposal
from app.models.trust_zones import TrustZone
from app.schemas.escalations import (
    CosignPayload,
    EscalationCosignerRead,
    EscalationCreate,
    EscalationRead,
    GovernanceEscalationCreate,
)
from app.services.escalation_engine import (
    add_cosigner,
    create_action_escalation,
    create_governance_escalation,
)
from app.services.audit import record_audit
from app.services.organizations import OrganizationContext
from app.services.permission_resolver import resolve_zone_permission
from app.services.zone_auth import ZoneAuthContext, require_zone_permission

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.core.auth import AuthContext

router = APIRouter(prefix="/organizations/me", tags=["escalations"])
SESSION_DEP = Depends(get_session)
AUTH_DEP = Depends(get_auth_context)
ORG_MEMBER_DEP = Depends(require_org_member)


async def _check_zone_perm(
    session: AsyncSession,
    member: object,
    zone_id: UUID,
    action: str,
) -> None:
    """Load zone and check permission, raising 403 on failure."""
    from app.models.organization_members import OrganizationMember

    zone = await TrustZone.objects.by_id(zone_id).first(session)
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
    if not isinstance(member, OrganizationMember):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    allowed = await resolve_zone_permission(
        session, member=member, zone=zone, action=action,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {action}",
        )


async def _get_escalation_or_404(
    session: AsyncSession,
    *,
    escalation_id: UUID,
    organization_id: UUID,
) -> Escalation:
    escalation = await Escalation.objects.by_id(escalation_id).first(session)
    if escalation is None or escalation.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return escalation


def _escalation_to_read(
    escalation: Escalation,
    cosigners: list[EscalationCosigner] | None = None,
) -> EscalationRead:
    model = EscalationRead.model_validate(escalation, from_attributes=True)
    if cosigners is not None:
        model.cosigners = [
            EscalationCosignerRead.model_validate(c, from_attributes=True)
            for c in cosigners
        ]
    return model


@router.post(
    "/proposals/{proposal_id}/escalate",
    response_model=EscalationRead,
)
async def escalate_proposal(
    proposal_id: UUID,
    payload: EscalationCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> EscalationRead:
    """Create an action escalation from a proposal to its parent zone."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # Load proposal to get zone_id for permission check
    proposal = await Proposal.objects.by_id(proposal_id).first(session)
    if proposal is None or proposal.organization_id != ctx.organization.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    await _check_zone_perm(session, ctx.member, proposal.zone_id, "escalation.trigger")

    escalation = await create_action_escalation(
        session,
        organization_id=ctx.organization.id,
        escalator_id=auth.user.id,
        proposal_id=proposal_id,
        reason=payload.reason,
    )

    cosigners = await EscalationCosigner.objects.filter_by(
        escalation_id=escalation.id,
    ).all(session)
    return _escalation_to_read(escalation, cosigners)


@router.post(
    "/zones/{zone_id}/escalate-governance",
    response_model=EscalationRead,
)
async def escalate_governance(
    zone_id: UUID,
    payload: GovernanceEscalationCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
    zone_ctx: ZoneAuthContext = require_zone_permission("escalation.trigger"),
) -> EscalationRead:
    """Create a governance escalation on a zone."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    escalation = await create_governance_escalation(
        session,
        organization_id=ctx.organization.id,
        escalator_id=auth.user.id,
        zone_id=zone_id,
        reason=payload.reason,
    )

    cosigners = await EscalationCosigner.objects.filter_by(
        escalation_id=escalation.id,
    ).all(session)
    return _escalation_to_read(escalation, cosigners)


@router.post(
    "/escalations/{escalation_id}/cosign",
    response_model=EscalationCosignerRead,
)
async def cosign_escalation(
    escalation_id: UUID,
    payload: CosignPayload,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> EscalationCosignerRead:
    """Add a co-signer to a governance escalation."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    escalation = await _get_escalation_or_404(
        session,
        escalation_id=escalation_id,
        organization_id=ctx.organization.id,
    )

    await _check_zone_perm(session, ctx.member, escalation.source_zone_id, "escalation.trigger")

    cosigner = await add_cosigner(
        session,
        escalation=escalation,
        user_id=auth.user.id,
    )

    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="escalation.cosign",
        zone_id=escalation.source_zone_id,
        target_type="escalation",
        target_id=escalation.id,
    )

    return EscalationCosignerRead.model_validate(cosigner, from_attributes=True)


@router.get("/escalations", response_model=list[EscalationRead])
async def list_escalations(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
    escalation_type: str | None = None,
    escalation_status: str | None = None,
) -> list[EscalationRead]:
    """List escalations in the active organization."""
    query = Escalation.objects.filter_by(organization_id=ctx.organization.id)
    if escalation_type is not None:
        query = query.filter_by(escalation_type=escalation_type)
    if escalation_status is not None:
        query = query.filter(col(Escalation.status) == escalation_status)
    escalations = await query.order_by(col(Escalation.created_at).desc()).all(session)
    return [_escalation_to_read(e) for e in escalations]


@router.get("/escalations/{escalation_id}", response_model=EscalationRead)
async def get_escalation(
    escalation_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> EscalationRead:
    """Get escalation detail with co-signers."""
    escalation = await _get_escalation_or_404(
        session,
        escalation_id=escalation_id,
        organization_id=ctx.organization.id,
    )
    cosigners = await EscalationCosigner.objects.filter_by(
        escalation_id=escalation.id,
    ).all(session)
    return _escalation_to_read(escalation, cosigners)
