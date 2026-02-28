"""Escalation engine service for action and governance escalation workflows."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sqlmodel import col

from app.core.logging import get_logger
from app.core.time import utcnow

logger = get_logger(__name__)
from app.models.escalations import Escalation, EscalationCosigner
from app.models.proposals import Proposal
from app.models.trust_zones import TrustZone
from app.models.zone_assignments import ZoneAssignment
from app.services.audit import record_audit
from app.services.governance_notifications.queue import GovernanceNotification, enqueue_notification

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

VALID_ESCALATION_STATUSES = {"pending", "accepted", "dismissed", "resolved"}


async def create_action_escalation(
    session: AsyncSession,
    *,
    organization_id: UUID,
    escalator_id: UUID,
    proposal_id: UUID,
    reason: str = "",
) -> Escalation:
    """Create an action escalation from a proposal to its parent zone.

    Pauses the original proposal and creates a new proposal in the parent zone.
    """
    proposal = await Proposal.objects.by_id(proposal_id).first(session)
    if proposal is None or proposal.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found in organization",
        )

    if proposal.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending proposals can be escalated",
        )

    zone = await TrustZone.objects.by_id(proposal.zone_id).first(session)
    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Source zone not found",
        )

    # Check rate limit
    await _check_rate_limit(
        session,
        escalator_id=escalator_id,
        zone=zone,
    )

    # Determine target zone (parent)
    if zone.parent_zone_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot escalate from root zone — no parent zone exists",
        )
    target_zone_id = zone.parent_zone_id

    now = utcnow()

    # Pause original proposal
    proposal.status = "escalated"
    proposal.updated_at = now
    session.add(proposal)

    escalation = Escalation(
        organization_id=organization_id,
        escalation_type="action",
        source_proposal_id=proposal.id,
        source_zone_id=zone.id,
        target_zone_id=target_zone_id,
        escalator_id=escalator_id,
        reason=reason,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(escalation)
    await session.flush()

    # Create a new proposal in the parent zone
    escalated_proposal = Proposal(
        organization_id=organization_id,
        zone_id=target_zone_id,
        proposer_id=escalator_id,
        title=f"[Escalated] {proposal.title}",
        description=f"Escalated from zone {zone.name}: {reason}" if reason else f"Escalated from zone {zone.name}",
        proposal_type=proposal.proposal_type,
        payload=proposal.payload,
        status="pending_review",
        created_at=now,
        updated_at=now,
        expires_at=proposal.expires_at,
    )
    session.add(escalated_proposal)
    await session.flush()

    escalation.resulting_proposal_id = escalated_proposal.id
    session.add(escalation)

    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=escalator_id,
        actor_type="human",
        action="escalation.action.create",
        zone_id=zone.id,
        target_type="escalation",
        target_id=escalation.id,
        payload={
            "source_proposal_id": str(proposal.id),
            "target_zone_id": str(target_zone_id),
        },
        commit=False,
    )

    await session.commit()
    await session.refresh(escalation)

    # Notify target zone approvers (fire-and-forget)
    try:
        target_approvers = await ZoneAssignment.objects.filter_by(
            zone_id=target_zone_id,
            role="approver",
        ).all(session)
        if target_approvers:
            enqueue_notification(GovernanceNotification(
                event_type="escalation_created",
                organization_id=organization_id,
                zone_id=zone.id,
                target_ids=[a.member_id for a in target_approvers],
                payload={
                    "escalation_id": str(escalation.id),
                    "escalation_type": "action",
                    "source_proposal_id": str(proposal.id),
                    "target_zone_id": str(target_zone_id),
                },
            ))
    except Exception:
        logger.warning("Failed to enqueue escalation_created notification", exc_info=True)

    return escalation


async def create_governance_escalation(
    session: AsyncSession,
    *,
    organization_id: UUID,
    escalator_id: UUID,
    zone_id: UUID,
    reason: str = "",
) -> Escalation:
    """Create a governance escalation on a zone.

    Governance escalations require co-signers before activation.
    """
    zone = await TrustZone.objects.by_id(zone_id).first(session)
    if zone is None or zone.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found in organization",
        )

    await _check_rate_limit(
        session,
        escalator_id=escalator_id,
        zone=zone,
    )

    if zone.parent_zone_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot escalate governance from root zone — no parent zone exists",
        )
    target_zone_id = zone.parent_zone_id

    now = utcnow()
    escalation = Escalation(
        organization_id=organization_id,
        escalation_type="governance",
        source_proposal_id=None,
        source_zone_id=zone.id,
        target_zone_id=target_zone_id,
        escalator_id=escalator_id,
        reason=reason,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(escalation)
    await session.flush()

    # Auto-add escalator as first co-signer
    cosigner = EscalationCosigner(
        escalation_id=escalation.id,
        user_id=escalator_id,
        created_at=now,
    )
    session.add(cosigner)

    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=escalator_id,
        actor_type="human",
        action="escalation.governance.create",
        zone_id=zone.id,
        target_type="escalation",
        target_id=escalation.id,
        commit=False,
    )

    await session.commit()
    await session.refresh(escalation)

    # Notify target zone approvers (fire-and-forget)
    try:
        target_approvers = await ZoneAssignment.objects.filter_by(
            zone_id=target_zone_id,
            role="approver",
        ).all(session)
        if target_approvers:
            enqueue_notification(GovernanceNotification(
                event_type="escalation_created",
                organization_id=organization_id,
                zone_id=zone.id,
                target_ids=[a.member_id for a in target_approvers],
                payload={
                    "escalation_id": str(escalation.id),
                    "escalation_type": "governance",
                    "target_zone_id": str(target_zone_id),
                },
            ))
    except Exception:
        logger.warning("Failed to enqueue governance escalation_created notification", exc_info=True)

    return escalation


async def add_cosigner(
    session: AsyncSession,
    *,
    escalation: Escalation,
    user_id: UUID,
) -> EscalationCosigner:
    """Add a co-signer to a governance escalation.

    If the co-signer threshold is met, activates the escalation
    by creating a meta-proposal in the parent zone.
    """
    if escalation.escalation_type != "governance":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Co-signing is only supported for governance escalations",
        )

    if escalation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Escalation is not pending",
        )

    # Check if already co-signed
    existing = await EscalationCosigner.objects.filter_by(
        escalation_id=escalation.id,
        user_id=user_id,
    ).all(session)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already co-signed this escalation",
        )

    now = utcnow()
    cosigner = EscalationCosigner(
        escalation_id=escalation.id,
        user_id=user_id,
        created_at=now,
    )
    session.add(cosigner)

    # Check if threshold is met
    all_cosigners = await EscalationCosigner.objects.filter_by(
        escalation_id=escalation.id,
    ).all(session)
    cosigner_count = len(all_cosigners) + 1  # include the one just added

    zone = await TrustZone.objects.by_id(escalation.source_zone_id).first(session)
    required = _get_cosigner_threshold(zone)

    if cosigner_count >= required:
        # Activate: create meta-proposal in target zone
        escalation.status = "accepted"
        escalation.updated_at = now

        meta_proposal = Proposal(
            organization_id=escalation.organization_id,
            zone_id=escalation.target_zone_id,
            proposer_id=escalation.escalator_id,
            title=f"[Governance Escalation] Zone policy review for {zone.name if zone else 'unknown'}",
            description=escalation.reason or "Governance escalation requiring review",
            proposal_type="zone_change",
            status="pending_review",
            created_at=now,
            updated_at=now,
        )
        session.add(meta_proposal)
        await session.flush()

        escalation.resulting_proposal_id = meta_proposal.id
        session.add(escalation)

    await session.commit()
    await session.refresh(cosigner)
    return cosigner


def _get_cosigner_threshold(zone: TrustZone | None) -> int:
    """Get the required number of co-signers from zone escalation policy."""
    if zone is None:
        return 2
    policy = zone.escalation_policy
    if policy and isinstance(policy.get("cosigner_threshold"), int):
        return max(1, policy["cosigner_threshold"])
    return 2  # default: 2 co-signers needed


async def check_auto_escalation(
    session: AsyncSession,
    *,
    proposal: Proposal,
) -> Escalation | None:
    """Check if a proposal should be auto-escalated due to timeout or deadlock.

    Returns the created escalation if auto-escalation triggered, else None.
    """
    zone = await TrustZone.objects.by_id(proposal.zone_id).first(session)
    if zone is None or zone.parent_zone_id is None:
        return None

    policy = zone.escalation_policy
    if policy is None:
        return None

    now = utcnow()

    # Check timeout-based auto-escalation
    auto_escalate_after_hours = policy.get("auto_escalate_after_hours")
    if auto_escalate_after_hours and isinstance(auto_escalate_after_hours, (int, float)):
        elapsed = (now - proposal.created_at).total_seconds() / 3600
        if elapsed >= auto_escalate_after_hours:
            escalation = Escalation(
                organization_id=proposal.organization_id,
                escalation_type="action",
                source_proposal_id=proposal.id,
                source_zone_id=zone.id,
                target_zone_id=zone.parent_zone_id,
                escalator_id=proposal.proposer_id,
                reason=f"Auto-escalated: exceeded {auto_escalate_after_hours}h timeout",
                status="accepted",
                created_at=now,
                updated_at=now,
            )
            session.add(escalation)

            proposal.status = "escalated"
            proposal.updated_at = now
            session.add(proposal)

            await session.commit()
            await session.refresh(escalation)
            return escalation

    return None


async def _check_rate_limit(
    session: AsyncSession,
    *,
    escalator_id: UUID,
    zone: TrustZone,
) -> None:
    """Enforce per-user escalation rate limits from zone's escalation_policy."""
    policy = zone.escalation_policy
    if policy is None:
        return

    max_per_day = policy.get("max_escalations_per_day")
    if not isinstance(max_per_day, int):
        return

    now = utcnow()
    one_day_ago = now - timedelta(hours=24)

    recent = await Escalation.objects.filter_by(
        escalator_id=escalator_id,
        source_zone_id=zone.id,
    ).filter(
        col(Escalation.created_at) >= one_day_ago,
    ).all(session)

    if len(recent) >= max_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Escalation rate limit exceeded: maximum {max_per_day} per day in this zone",
        )
