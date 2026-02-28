"""Proposal management endpoints for zone-scoped approval workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col

from app.api.deps import require_org_member
from app.core.auth import AuthContext, get_auth_context
from app.db.session import get_session
from app.models.approval_requests import ApprovalRequest
from app.models.proposals import Proposal
from app.models.trust_zones import TrustZone
from app.schemas.common import OkResponse
from app.schemas.proposals import (
    ApprovalRequestRead,
    ProposalCreate,
    ProposalRead,
    VotePayload,
)
from app.services.approval_engine import create_proposal, record_decision
from app.services.audit import record_audit
from app.services.organizations import OrganizationContext
from app.services.permission_resolver import check_resource_scope, resolve_zone_permission

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/organizations/me/proposals", tags=["proposals"])
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


async def _get_proposal_or_404(
    session: AsyncSession,
    *,
    proposal_id: UUID,
    organization_id: UUID,
) -> Proposal:
    proposal = await Proposal.objects.by_id(proposal_id).first(session)
    if proposal is None or proposal.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return proposal


def _proposal_to_read(
    proposal: Proposal,
    approval_requests: list[ApprovalRequest] | None = None,
) -> ProposalRead:
    model = ProposalRead.model_validate(proposal, from_attributes=True)
    if approval_requests is not None:
        model.approval_requests = [
            ApprovalRequestRead.model_validate(r, from_attributes=True)
            for r in approval_requests
        ]
    return model


@router.post("", response_model=ProposalRead)
async def create_proposal_endpoint(
    payload: ProposalCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> ProposalRead:
    """Create a new proposal in a trust zone."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    await _check_zone_perm(session, ctx.member, payload.zone_id, "proposal.create")

    # Early resource scope validation for resource_allocation proposals
    if payload.proposal_type == "resource_allocation" and payload.payload:
        zone = await TrustZone.objects.by_id(payload.zone_id).first(session)
        if zone is not None:
            resource_ctx: dict[str, object] = {}
            for key in ("budget_amount", "board_id", "agent_type"):
                val = payload.payload.get(key)
                if val is not None:
                    resource_ctx[key] = val
            if resource_ctx:
                allowed, reason = check_resource_scope(zone, resource_ctx)
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Resource scope violation: {reason}",
                    )

    proposal = await create_proposal(
        session,
        organization_id=ctx.organization.id,
        proposer_id=auth.user.id,
        payload=payload,
    )

    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="proposal.create",
        zone_id=proposal.zone_id,
        target_type="proposal",
        target_id=proposal.id,
    )

    requests = await ApprovalRequest.objects.filter_by(
        proposal_id=proposal.id,
    ).all(session)
    return _proposal_to_read(proposal, requests)


@router.get("/pending-reviews", response_model=list[ProposalRead])
async def list_pending_reviews(
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> list[ProposalRead]:
    """Proposals where the current member has undecided ApprovalRequests."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    # Find all approval requests assigned to this member that are undecided
    undecided_requests = await ApprovalRequest.objects.filter_by(
        reviewer_id=ctx.member.id,
    ).filter(
        col(ApprovalRequest.decision) == None,  # noqa: E711
    ).all(session)

    if not undecided_requests:
        return []

    # Get the associated proposals that are pending_review and belong to the org
    proposal_ids = {r.proposal_id for r in undecided_requests}
    result: list[ProposalRead] = []
    for pid in proposal_ids:
        proposal = await Proposal.objects.by_id(pid).first(session)
        if (
            proposal is not None
            and proposal.organization_id == ctx.organization.id
            and proposal.status == "pending_review"
        ):
            requests = await ApprovalRequest.objects.filter_by(
                proposal_id=proposal.id,
            ).all(session)
            result.append(_proposal_to_read(proposal, requests))

    return result


@router.get("", response_model=list[ProposalRead])
async def list_proposals(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
    zone_id: UUID | None = None,
    proposal_status: str | None = None,
) -> list[ProposalRead]:
    """List proposals in the active organization."""
    query = Proposal.objects.filter_by(organization_id=ctx.organization.id)
    if zone_id is not None:
        query = query.filter_by(zone_id=zone_id)
    if proposal_status is not None:
        query = query.filter(col(Proposal.status) == proposal_status)
    proposals = await query.order_by(col(Proposal.created_at).desc()).all(session)
    return [_proposal_to_read(p) for p in proposals]


@router.get("/{proposal_id}", response_model=ProposalRead)
async def get_proposal(
    proposal_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> ProposalRead:
    """Get proposal detail with approval requests."""
    proposal = await _get_proposal_or_404(
        session, proposal_id=proposal_id, organization_id=ctx.organization.id
    )
    requests = await ApprovalRequest.objects.filter_by(
        proposal_id=proposal.id,
    ).all(session)
    return _proposal_to_read(proposal, requests)


@router.post("/{proposal_id}/approve", response_model=ApprovalRequestRead)
async def approve_proposal(
    proposal_id: UUID,
    payload: VotePayload,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> ApprovalRequestRead:
    """Vote approve on a proposal."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    proposal = await _get_proposal_or_404(
        session, proposal_id=proposal_id, organization_id=ctx.organization.id
    )
    await _check_zone_perm(session, ctx.member, proposal.zone_id, "proposal.approve")
    if proposal.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proposal is not pending review",
        )
    request = await record_decision(
        session,
        proposal=proposal,
        reviewer_id=ctx.member.id,
        decision="approve",
        rationale=payload.rationale,
    )
    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="proposal.approve",
        zone_id=proposal.zone_id,
        target_type="proposal",
        target_id=proposal.id,
    )
    return ApprovalRequestRead.model_validate(request, from_attributes=True)


@router.post("/{proposal_id}/reject", response_model=ApprovalRequestRead)
async def reject_proposal(
    proposal_id: UUID,
    payload: VotePayload,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> ApprovalRequestRead:
    """Vote reject on a proposal."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    proposal = await _get_proposal_or_404(
        session, proposal_id=proposal_id, organization_id=ctx.organization.id
    )
    await _check_zone_perm(session, ctx.member, proposal.zone_id, "proposal.reject")
    if proposal.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proposal is not pending review",
        )
    request = await record_decision(
        session,
        proposal=proposal,
        reviewer_id=ctx.member.id,
        decision="reject",
        rationale=payload.rationale,
    )
    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="proposal.reject",
        zone_id=proposal.zone_id,
        target_type="proposal",
        target_id=proposal.id,
    )
    return ApprovalRequestRead.model_validate(request, from_attributes=True)


@router.post("/{proposal_id}/abstain", response_model=ApprovalRequestRead)
async def abstain_proposal(
    proposal_id: UUID,
    payload: VotePayload,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> ApprovalRequestRead:
    """Vote abstain on a proposal."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    proposal = await _get_proposal_or_404(
        session, proposal_id=proposal_id, organization_id=ctx.organization.id
    )
    await _check_zone_perm(session, ctx.member, proposal.zone_id, "proposal.review")
    if proposal.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proposal is not pending review",
        )
    request = await record_decision(
        session,
        proposal=proposal,
        reviewer_id=ctx.member.id,
        decision="abstain",
        rationale=payload.rationale,
    )
    return ApprovalRequestRead.model_validate(request, from_attributes=True)
