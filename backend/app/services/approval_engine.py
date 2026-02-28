"""Approval engine service for proposal creation, review, and decision evaluation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from app.core.time import utcnow
from app.models.approval_requests import ApprovalRequest
from app.models.gardener_feedback import GardenerFeedback
from app.models.proposals import Proposal
from app.models.trust_zones import TrustZone
from app.models.zone_assignments import ZoneAssignment
from app.core.logging import get_logger
from app.services.audit import record_audit
from app.services.governance_notifications.queue import GovernanceNotification, enqueue_notification
from app.services.permission_resolver import check_resource_scope

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.schemas.proposals import ProposalCreate

logger = get_logger(__name__)

VALID_PROPOSAL_TYPES = {
    "task_execution",
    "resource_allocation",
    "zone_change",
    "membership_change",
}


async def create_proposal(
    session: AsyncSession,
    *,
    organization_id: UUID,
    proposer_id: UUID,
    payload: ProposalCreate,
) -> Proposal:
    """Create a proposal and select initial reviewers."""
    if payload.proposal_type not in VALID_PROPOSAL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid proposal_type. Must be one of: {', '.join(sorted(VALID_PROPOSAL_TYPES))}",
        )

    zone = await TrustZone.objects.by_id(payload.zone_id).first(session)
    if zone is None or zone.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Zone not found in organization",
        )

    # Validate resource scope for resource_allocation proposals
    if payload.proposal_type == "resource_allocation" and payload.payload:
        resource_ctx: dict[str, object] = {}
        budget_amount = payload.payload.get("budget_amount")
        if budget_amount is not None:
            resource_ctx["budget_amount"] = budget_amount
        board_id = payload.payload.get("board_id")
        if board_id is not None:
            resource_ctx["board_id"] = board_id
        agent_type = payload.payload.get("agent_type")
        if agent_type is not None:
            resource_ctx["agent_type"] = agent_type
        if resource_ctx:
            allowed, reason = check_resource_scope(zone, resource_ctx)
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Resource scope violation: {reason}",
                )

    now = utcnow()
    proposal = Proposal(
        organization_id=organization_id,
        zone_id=payload.zone_id,
        proposer_id=proposer_id,
        title=payload.title,
        description=payload.description,
        proposal_type=payload.proposal_type,
        payload=payload.payload,
        status="pending_review",
        decision_model_override=payload.decision_model_override,
        expires_at=payload.expires_at,
        created_at=now,
        updated_at=now,
    )
    session.add(proposal)
    await session.flush()

    # Auto-approve check
    if check_auto_approve(zone=zone, proposal=proposal):
        proposal.status = "approved"
        proposal.resolved_at = now
        session.add(proposal)
        await session.commit()
        await session.refresh(proposal)
        return proposal

    # Select reviewers
    reviewers = await select_reviewers(session, zone=zone, proposal=proposal)
    for reviewer_id, reason in reviewers:
        request = ApprovalRequest(
            proposal_id=proposal.id,
            reviewer_id=reviewer_id,
            reviewer_type="human",
            selection_reason=reason,
            created_at=now,
        )
        session.add(request)

    await session.commit()
    await session.refresh(proposal)

    # Notify selected reviewers (fire-and-forget)
    if reviewers:
        try:
            enqueue_notification(GovernanceNotification(
                event_type="reviewers_selected",
                organization_id=organization_id,
                zone_id=payload.zone_id,
                target_ids=[rid for rid, _ in reviewers],
                payload={
                    "proposal_id": str(proposal.id),
                    "title": proposal.title,
                    "proposal_type": proposal.proposal_type,
                },
            ))
        except Exception:
            logger.warning("Failed to enqueue reviewers_selected notification", exc_info=True)

    return proposal


async def select_reviewers(
    session: AsyncSession,
    *,
    zone: TrustZone,
    proposal: Proposal,
) -> list[tuple[UUID, str]]:
    """Select reviewers for a proposal based on zone config and assignments.

    Returns list of (reviewer_id, selection_reason) tuples.
    """
    reviewers: list[tuple[UUID, str]] = []

    # Check zone's approval_policy for static reviewers
    if zone.approval_policy and isinstance(
        zone.approval_policy.get("static_reviewers"), list
    ):
        from uuid import UUID as _UUID

        for reviewer_str in zone.approval_policy["static_reviewers"]:
            try:
                rid = _UUID(str(reviewer_str))
                reviewers.append((rid, "static_reviewer_from_zone_policy"))
            except ValueError:
                continue

    # Gap 2: Try Gardener AI selection if strategy is "gardener"
    if not reviewers and zone.approval_policy and zone.approval_policy.get("reviewer_selection_strategy") == "gardener":
        try:
            from app.services.gardener import GardenerService, build_candidates

            candidates = await build_candidates(
                session, zone=zone, exclude_user_id=proposal.proposer_id,
            )
            if candidates:
                gardener = GardenerService()
                selections = await gardener.select_reviewers(
                    session, proposal=proposal, zone=zone, candidates=candidates,
                )
                for selection in selections:
                    reviewers.append((selection.reviewer_id, selection.reason))
        except Exception:
            logger.warning(
                "Gardener reviewer selection failed, falling back to rule-based",
                exc_info=True,
            )

    if not reviewers:
        # Fall back to zone approver assignments
        assignments = await ZoneAssignment.objects.filter_by(
            zone_id=zone.id,
            role="approver",
        ).all(session)
        for assignment in assignments:
            reviewers.append(
                (assignment.member_id, "zone_approver_assignment")
            )

    if not reviewers:
        # Fall back to gardener assignments
        gardeners = await ZoneAssignment.objects.filter_by(
            zone_id=zone.id,
            role="gardener",
        ).all(session)
        for g in gardeners:
            reviewers.append((g.member_id, "zone_gardener_fallback"))

    return reviewers


def check_auto_approve(*, zone: TrustZone, proposal: Proposal) -> bool:
    """Check if a proposal should be auto-approved based on zone policy."""
    if zone.approval_policy is None:
        return False
    auto_approve = zone.approval_policy.get("auto_approve_types")
    if isinstance(auto_approve, list) and proposal.proposal_type in auto_approve:
        return True
    return False


async def record_decision(
    session: AsyncSession,
    *,
    proposal: Proposal,
    reviewer_id: UUID,
    decision: str,
    rationale: str = "",
) -> ApprovalRequest:
    """Record a reviewer's decision on a proposal."""
    requests = await ApprovalRequest.objects.filter_by(
        proposal_id=proposal.id,
        reviewer_id=reviewer_id,
    ).all(session)

    if not requests:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not an assigned reviewer for this proposal",
        )

    request = requests[0]
    if request.decision is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already voted on this proposal",
        )

    now = utcnow()
    request.decision = decision
    request.rationale = rationale
    request.decided_at = now
    session.add(request)

    # Evaluate decision model
    await _evaluate_and_resolve(session, proposal=proposal)

    await session.commit()
    await session.refresh(request)
    return request


async def _evaluate_and_resolve(
    session: AsyncSession,
    *,
    proposal: Proposal,
) -> None:
    """Evaluate the decision model and resolve the proposal if criteria met."""
    all_requests = await ApprovalRequest.objects.filter_by(
        proposal_id=proposal.id,
    ).all(session)

    decided = [r for r in all_requests if r.decision is not None]
    if not decided:
        return

    # Get decision model from override or zone
    dm = proposal.decision_model_override
    if dm is None:
        zone = await TrustZone.objects.by_id(proposal.zone_id).first(session)
        dm = zone.decision_model if zone else None
    if dm is None:
        dm = {"model_type": "threshold", "threshold": 1}

    model_type = dm.get("model_type", "threshold")
    now = utcnow()

    if model_type == "unilateral":
        # First vote decides
        first_vote = decided[0]
        proposal.status = "approved" if first_vote.decision == "approve" else "rejected"
        proposal.resolved_at = now

    elif model_type == "threshold":
        threshold = int(dm.get("threshold", 1))
        approvals = sum(1 for r in decided if r.decision == "approve")
        rejections = sum(1 for r in decided if r.decision == "reject")
        if approvals >= threshold:
            proposal.status = "approved"
            proposal.resolved_at = now
        elif rejections >= threshold:
            proposal.status = "rejected"
            proposal.resolved_at = now

    elif model_type == "majority":
        total = len(all_requests)
        if len(decided) == total:
            approvals = sum(1 for r in decided if r.decision == "approve")
            if approvals > total / 2:
                proposal.status = "approved"
            else:
                proposal.status = "rejected"
            proposal.resolved_at = now

    elif model_type == "weighted":
        # Simple weighted: approver weight=2, others weight=1
        score = 0.0
        for r in decided:
            weight = 1.0
            if r.decision == "approve":
                score += weight
            elif r.decision == "reject":
                score -= weight
        if len(decided) == len(all_requests):
            proposal.status = "approved" if score > 0 else "rejected"
            proposal.resolved_at = now

    elif model_type == "consensus":
        approvals = sum(1 for r in decided if r.decision == "approve")
        rejections = sum(1 for r in decided if r.decision == "reject")
        if approvals == len(all_requests):
            proposal.status = "approved"
            proposal.resolved_at = now
        elif rejections > 0:
            # Consensus broken, fall back to threshold
            fallback_threshold = int(dm.get("threshold", 1))
            if approvals >= fallback_threshold:
                proposal.status = "approved"
            else:
                proposal.status = "rejected"
            proposal.resolved_at = now

    if proposal.resolved_at is not None:
        proposal.updated_at = now

        # Gap 3: Execute payload on approval
        if proposal.status == "approved":
            await execute_proposal(session, proposal=proposal)

        # Gap 5: Record gardener feedback after resolution
        await _record_gardener_feedback(session, proposal=proposal)

        session.add(proposal)

        # Notify proposer and reviewers of resolution (fire-and-forget)
        try:
            reviewer_ids = [r.reviewer_id for r in all_requests]
            enqueue_notification(GovernanceNotification(
                event_type="proposal_resolved",
                organization_id=proposal.organization_id,
                zone_id=proposal.zone_id,
                target_ids=[proposal.proposer_id] + reviewer_ids,
                payload={
                    "proposal_id": str(proposal.id),
                    "title": proposal.title,
                    "status": proposal.status,
                },
            ))
        except Exception:
            logger.warning("Failed to enqueue proposal_resolved notification", exc_info=True)


async def execute_proposal(
    session: AsyncSession,
    *,
    proposal: Proposal,
) -> None:
    """Execute a proposal's payload after approval.

    Dispatches based on proposal_type to perform the actual work.
    """
    payload = proposal.payload or {}

    if proposal.proposal_type == "zone_change":
        zone_id = payload.get("zone_id") or proposal.zone_id
        updates = payload.get("updates")
        if isinstance(updates, dict):
            from app.models.trust_zones import TrustZone as _TZ

            zone = await _TZ.objects.by_id(zone_id).first(session)
            if zone is not None:
                for key, value in updates.items():
                    if hasattr(zone, key):
                        setattr(zone, key, value)
                zone.updated_at = utcnow()
                session.add(zone)
                logger.info("Executed zone_change proposal %s on zone %s", proposal.id, zone_id)

    elif proposal.proposal_type == "membership_change":
        action = payload.get("action")
        zone_id = payload.get("zone_id") or proposal.zone_id
        member_id = payload.get("member_id")
        role = payload.get("role", "executor")

        if action == "add" and member_id:
            from uuid import UUID as _UUID

            assignment = ZoneAssignment(
                zone_id=_UUID(str(zone_id)),
                member_id=_UUID(str(member_id)),
                role=str(role),
                assigned_by=proposal.proposer_id,
            )
            session.add(assignment)
            logger.info("Executed membership_change (add) proposal %s", proposal.id)

        elif action == "remove" and member_id:
            from uuid import UUID as _UUID

            existing = await ZoneAssignment.objects.filter_by(
                zone_id=_UUID(str(zone_id)),
                member_id=_UUID(str(member_id)),
                role=str(role),
            ).all(session)
            for a in existing:
                await session.delete(a)
            logger.info("Executed membership_change (remove) proposal %s", proposal.id)

    elif proposal.proposal_type == "resource_allocation":
        # Verify resource scope at execution time
        zone = await TrustZone.objects.by_id(proposal.zone_id).first(session)
        if zone is not None and payload.get("budget_amount") is not None:
            allowed, reason = check_resource_scope(zone, {
                "budget_amount": payload["budget_amount"],
            })
            if not allowed:
                logger.warning(
                    "Resource scope violation at execution: %s (proposal %s)",
                    reason,
                    proposal.id,
                )
                # Skip execution but don't fail — proposal stays approved, external handling expected
        logger.info(
            "Proposal %s of type resource_allocation approved — external execution expected",
            proposal.id,
        )

    elif proposal.proposal_type == "task_execution":
        logger.info(
            "Proposal %s of type task_execution approved — external execution expected",
            proposal.id,
        )

    await record_audit(
        session,
        organization_id=proposal.organization_id,
        actor_id=proposal.proposer_id,
        actor_type="system",
        action="proposal.execute",
        zone_id=proposal.zone_id,
        target_type="proposal",
        target_id=proposal.id,
        payload=payload,
        commit=False,
    )


async def _record_gardener_feedback(
    session: AsyncSession,
    *,
    proposal: Proposal,
) -> None:
    """Update GardenerFeedback entries after a proposal reaches a terminal state."""
    feedback_entries = await GardenerFeedback.objects.filter_by(
        proposal_id=proposal.id,
    ).all(session)

    if not feedback_entries:
        return

    approval_requests = await ApprovalRequest.objects.filter_by(
        proposal_id=proposal.id,
    ).all(session)
    decisions_by_reviewer = {
        r.reviewer_id: r for r in approval_requests
    }

    now = utcnow()
    for entry in feedback_entries:
        request = decisions_by_reviewer.get(entry.reviewer_id)
        if request is not None:
            entry.reviewed_in_time = request.decided_at is not None
            # Decision overturned: reviewer voted one way but outcome was opposite
            if request.decision is not None:
                reviewer_approved = request.decision == "approve"
                proposal_approved = proposal.status == "approved"
                entry.decision_overturned = reviewer_approved != proposal_approved
        else:
            entry.reviewed_in_time = False

        entry.work_outcome = proposal.status
        entry.updated_at = now
        session.add(entry)
