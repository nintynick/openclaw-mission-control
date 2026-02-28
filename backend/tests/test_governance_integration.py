# ruff: noqa: INP001
"""Integration tests for the full governance lifecycle using an in-memory SQLite DB.

Tests exercise real SQL queries, FK constraints, and the full service chain
(create zone → assign members → create proposal → vote → resolve → evaluate).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Import all models so their tables are registered in SQLModel.metadata
from app.models.approval_requests import ApprovalRequest
from app.models.approvals import Approval  # noqa: F401 – FK target for proposals.legacy_approval_id
from app.models.audit_entries import AuditEntry  # noqa: F401 – created by record_audit
from app.models.escalations import Escalation, EscalationCosigner
from app.models.evaluations import Evaluation, EvaluationScore, IncentiveSignal
from app.models.gardener_feedback import GardenerFeedback
from app.models.organization_members import OrganizationMember
from app.models.organizations import Organization
from app.models.proposals import Proposal
from app.models.trust_zones import TrustZone
from app.models.users import User
from app.models.zone_assignments import ZoneAssignment

from app.services.approval_engine import (
    _record_gardener_feedback,
    create_proposal,
    execute_proposal,
    record_decision,
    select_reviewers,
)
from app.services.evaluations import (
    SYSTEM_EVALUATOR_ID,
    apply_incentive_signals,
    auto_evaluate,
    create_evaluation,
    finalize_evaluation,
    generate_reviewer_incentive_signals,
    submit_score,
)
from app.services.permission_resolver import check_resource_scope, resolve_zone_permission
from app.services.gardener import ReviewerCandidate, build_candidates

# Minimal schema stubs needed by create_proposal / create_evaluation
from app.schemas.proposals import ProposalCreate
from app.schemas.evaluations import EvaluationCreate, EvaluationScoreCreate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

async def _make_engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.connect() as conn, conn.begin():
        await conn.run_sync(SQLModel.metadata.create_all)
    return engine


async def _make_session(engine: AsyncEngine) -> AsyncSession:
    return AsyncSession(engine, expire_on_commit=False)


async def _seed_org_and_zone(
    session: AsyncSession,
    *,
    approval_policy: dict | None = None,
    decision_model: dict | None = None,
    parent_zone_id: UUID | None = None,
) -> tuple[Organization, User, OrganizationMember, TrustZone]:
    """Create an org, user, org_member, and trust_zone for testing."""
    org = Organization(name="test-org")
    session.add(org)
    await session.flush()

    user = User(clerk_user_id=f"clerk_{uuid4().hex[:12]}", email="test@example.com", name="Tester")
    session.add(user)
    await session.flush()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="member",
    )
    session.add(member)
    await session.flush()

    zone = TrustZone(
        organization_id=org.id,
        parent_zone_id=parent_zone_id,
        name="test-zone",
        slug="test-zone",
        created_by=user.id,
        approval_policy=approval_policy or {},
        decision_model=decision_model or {"model_type": "threshold", "threshold": 1},
    )
    session.add(zone)
    await session.flush()

    return org, user, member, zone


async def _create_approver(
    session: AsyncSession,
    org: Organization,
    zone: TrustZone,
    assigner: User,
) -> tuple[User, OrganizationMember, ZoneAssignment]:
    """Create a user with an approver role assignment in the given zone."""
    user = User(clerk_user_id=f"clerk_{uuid4().hex[:12]}", email=f"approver-{uuid4().hex[:6]}@example.com")
    session.add(user)
    await session.flush()

    member = OrganizationMember(
        organization_id=org.id,
        user_id=user.id,
        role="member",
    )
    session.add(member)
    await session.flush()

    assignment = ZoneAssignment(
        zone_id=zone.id,
        member_id=member.id,
        role="approver",
        assigned_by=assigner.id,
    )
    session.add(assignment)
    await session.flush()

    return user, member, assignment


# ---------------------------------------------------------------------------
# Test 1: Proposal approval lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proposal_approval_lifecycle() -> None:
    """Create proposal → approve → verify status approved + execute_proposal runs."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)

            # Create approver
            approver_user, approver_member, _ = await _create_approver(
                session, org, zone, user,
            )
            await session.commit()

            # Create proposal
            payload = ProposalCreate(
                zone_id=zone.id,
                title="Add feature X",
                description="Implement feature X",
                proposal_type="task_execution",
            )
            proposal = await create_proposal(
                session,
                organization_id=org.id,
                proposer_id=user.id,
                payload=payload,
            )
            assert proposal.status == "pending_review"

            # Verify approval request was created for approver
            requests = await ApprovalRequest.objects.filter_by(
                proposal_id=proposal.id,
            ).all(session)
            assert len(requests) >= 1
            reviewer_ids = {r.reviewer_id for r in requests}
            assert approver_member.id in reviewer_ids

            # Record approve decision
            request = await record_decision(
                session,
                proposal=proposal,
                reviewer_id=approver_member.id,
                decision="approve",
                rationale="Looks good",
            )
            assert request.decision == "approve"

            # Reload proposal to check resolved status
            refreshed = await Proposal.objects.by_id(proposal.id).first(session)
            assert refreshed is not None
            assert refreshed.status == "approved"
            assert refreshed.resolved_at is not None
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 2: Proposal rejection with threshold
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proposal_rejection_with_threshold() -> None:
    """threshold=2 → 1 reject → still pending → 2nd reject → rejected."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(
                session,
                decision_model={"model_type": "threshold", "threshold": 2},
            )
            # Two approvers
            _, approver1, _ = await _create_approver(session, org, zone, user)
            _, approver2, _ = await _create_approver(session, org, zone, user)
            await session.commit()

            payload = ProposalCreate(
                zone_id=zone.id,
                title="Risky change",
                proposal_type="zone_change",
            )
            proposal = await create_proposal(
                session,
                organization_id=org.id,
                proposer_id=user.id,
                payload=payload,
            )
            assert proposal.status == "pending_review"

            # First reject
            await record_decision(
                session,
                proposal=proposal,
                reviewer_id=approver1.id,
                decision="reject",
                rationale="Too risky",
            )
            refreshed = await Proposal.objects.by_id(proposal.id).first(session)
            assert refreshed is not None
            assert refreshed.status == "pending_review"  # threshold not met

            # Second reject
            await record_decision(
                session,
                proposal=proposal,
                reviewer_id=approver2.id,
                decision="reject",
                rationale="Agree, too risky",
            )
            refreshed = await Proposal.objects.by_id(proposal.id).first(session)
            assert refreshed is not None
            assert refreshed.status == "rejected"
            assert refreshed.resolved_at is not None
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 3: Escalation creates parent proposal
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_escalation_creates_parent_proposal() -> None:
    """Escalate from child zone → verify new proposal in parent zone, original paused."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            # Create parent zone
            org, user, member, parent_zone = await _seed_org_and_zone(session)

            # Create child zone
            child_zone = TrustZone(
                organization_id=org.id,
                parent_zone_id=parent_zone.id,
                name="child-zone",
                slug="child-zone",
                created_by=user.id,
                approval_policy={},
                decision_model={"model_type": "threshold", "threshold": 1},
            )
            session.add(child_zone)
            await session.flush()

            # Create approver in child zone
            _, approver_member, _ = await _create_approver(
                session, org, child_zone, user,
            )
            await session.commit()

            # Create proposal in child zone
            payload = ProposalCreate(
                zone_id=child_zone.id,
                title="Child proposal",
                proposal_type="task_execution",
            )
            proposal = await create_proposal(
                session,
                organization_id=org.id,
                proposer_id=user.id,
                payload=payload,
            )
            assert proposal.status == "pending_review"

            # Escalate
            from app.services.escalation_engine import create_action_escalation

            escalation = await create_action_escalation(
                session,
                organization_id=org.id,
                escalator_id=user.id,
                proposal_id=proposal.id,
                reason="Needs higher authority",
            )

            assert escalation.source_zone_id == child_zone.id
            assert escalation.target_zone_id == parent_zone.id
            assert escalation.resulting_proposal_id is not None

            # Original proposal should be escalated (paused)
            original = await Proposal.objects.by_id(proposal.id).first(session)
            assert original is not None
            assert original.status == "escalated"

            # New proposal in parent zone
            new_proposal = await Proposal.objects.by_id(
                escalation.resulting_proposal_id
            ).first(session)
            assert new_proposal is not None
            assert new_proposal.zone_id == parent_zone.id
            assert new_proposal.status == "pending_review"
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 4: Evaluation finalize updates reputation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_evaluation_finalize_updates_reputation() -> None:
    """Create evaluation → submit scores → finalize → verify reputation updated."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)

            # Create executor
            executor_user = User(
                clerk_user_id=f"clerk_{uuid4().hex[:12]}",
                email="executor@example.com",
            )
            session.add(executor_user)
            await session.flush()

            executor_member = OrganizationMember(
                organization_id=org.id,
                user_id=executor_user.id,
                role="member",
                reputation_score=5.0,
            )
            session.add(executor_member)
            await session.flush()

            # Create evaluator assignment
            evaluator_assignment = ZoneAssignment(
                zone_id=zone.id,
                member_id=member.id,
                role="evaluator",
                assigned_by=user.id,
            )
            session.add(evaluator_assignment)
            await session.commit()

            # Create evaluation
            eval_payload = EvaluationCreate(
                zone_id=zone.id,
                executor_id=executor_member.id,
            )
            evaluation = await create_evaluation(
                session,
                organization_id=org.id,
                creator_id=user.id,
                payload=eval_payload,
            )
            assert evaluation.status == "pending"

            # Submit score (high score → positive signal)
            score_payload = EvaluationScoreCreate(
                criterion_name="quality",
                criterion_weight=1.0,
                score=0.9,
                rationale="Great work",
            )
            score = await submit_score(
                session,
                evaluation=evaluation,
                evaluator_id=member.id,
                payload=score_payload,
            )
            assert score.score == 0.9

            # Finalize
            evaluation = await finalize_evaluation(
                session,
                evaluation=evaluation,
                finalized_by=user.id,
            )
            assert evaluation.status == "completed"
            assert evaluation.aggregate_result is not None
            assert evaluation.aggregate_result["overall_score"] == 0.9

            # Apply incentive signals
            applied = await apply_incentive_signals(session, evaluation=evaluation)
            assert applied >= 1

            # Verify reputation updated
            refreshed_executor = await OrganizationMember.objects.by_id(
                executor_member.id
            ).first(session)
            assert refreshed_executor is not None
            assert refreshed_executor.reputation_score > 5.0  # positive signal increased it
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 5: Permission resolver zone tree walk
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_permission_resolver_zone_tree_walk() -> None:
    """Verify permission resolution walks zone ancestry to parent and falls back to org role."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, parent_zone = await _seed_org_and_zone(session)

            # Create child zone
            child_zone = TrustZone(
                organization_id=org.id,
                parent_zone_id=parent_zone.id,
                name="child",
                slug="child",
                created_by=user.id,
            )
            session.add(child_zone)
            await session.flush()

            # Assign approver role in PARENT zone
            approver_user, approver_member, _ = await _create_approver(
                session, org, parent_zone, user,
            )
            await session.commit()

            # Approver should have "proposal.approve" in child zone via tree walk
            has_perm = await resolve_zone_permission(
                session,
                member=approver_member,
                zone=child_zone,
                action="proposal.approve",
            )
            assert has_perm is True

            # Regular member should be able to create proposals (org-level permission)
            has_create = await resolve_zone_permission(
                session,
                member=member,
                zone=child_zone,
                action="proposal.create",
            )
            assert has_create is True

            # Regular member should NOT have approve permission
            has_approve = await resolve_zone_permission(
                session,
                member=member,
                zone=child_zone,
                action="proposal.approve",
            )
            assert has_approve is False
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 6: Gardener feedback recorded after resolution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gardener_feedback_recorded() -> None:
    """Verify GardenerFeedback rows are updated after proposal resolves."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)

            # Create approver
            _, approver_member, _ = await _create_approver(
                session, org, zone, user,
            )
            await session.commit()

            # Create proposal
            payload = ProposalCreate(
                zone_id=zone.id,
                title="Test feedback tracking",
                proposal_type="task_execution",
            )
            proposal = await create_proposal(
                session,
                organization_id=org.id,
                proposer_id=user.id,
                payload=payload,
            )

            # Manually create a GardenerFeedback entry (simulating gardener selection)
            from app.core.time import utcnow

            feedback = GardenerFeedback(
                proposal_id=proposal.id,
                reviewer_id=approver_member.id,
                selected_by="gardener_ai",
            )
            session.add(feedback)
            await session.commit()

            # Approve the proposal (triggers _record_gardener_feedback)
            await record_decision(
                session,
                proposal=proposal,
                reviewer_id=approver_member.id,
                decision="approve",
                rationale="Approved for testing",
            )

            # Verify feedback was updated
            updated_feedback = await GardenerFeedback.objects.filter_by(
                proposal_id=proposal.id,
            ).all(session)
            assert len(updated_feedback) == 1
            fb = updated_feedback[0]
            assert fb.reviewed_in_time is True
            assert fb.decision_overturned is False  # approved and proposal approved
            assert fb.work_outcome == "approved"
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 7: Governance notifications enqueue (fire-and-forget)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_notification_enqueue_does_not_block() -> None:
    """Notifications failing should never block proposal creation."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)
            _, approver_member, _ = await _create_approver(session, org, zone, user)
            await session.commit()

            # Create proposal — notification enqueue will fail (no Redis)
            # but the proposal should still be created successfully
            payload = ProposalCreate(
                zone_id=zone.id,
                title="Test with notifications",
                proposal_type="task_execution",
            )
            proposal = await create_proposal(
                session,
                organization_id=org.id,
                proposer_id=user.id,
                payload=payload,
            )
            assert proposal.status == "pending_review"
            assert proposal.id is not None
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 8: Resource scope enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resource_scope_blocks_over_budget() -> None:
    """resource_scope.budget_limit blocks proposals exceeding the limit."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)

            # Set resource scope with budget limit
            zone.resource_scope = {"budget_limit": 1000}
            session.add(zone)
            await session.commit()

            # Check directly
            allowed, reason = check_resource_scope(zone, {"budget_amount": 500})
            assert allowed is True
            assert reason == ""

            allowed, reason = check_resource_scope(zone, {"budget_amount": 1500})
            assert allowed is False
            assert "exceeds" in reason.lower()

            # Proposal creation should fail for over-budget
            from fastapi import HTTPException

            payload = ProposalCreate(
                zone_id=zone.id,
                title="Over budget request",
                proposal_type="resource_allocation",
                payload={"budget_amount": 2000},
            )
            with pytest.raises(HTTPException) as exc_info:
                await create_proposal(
                    session,
                    organization_id=org.id,
                    proposer_id=user.id,
                    payload=payload,
                )
            assert exc_info.value.status_code == 422
            assert "resource scope" in str(exc_info.value.detail).lower()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_resource_scope_allows_within_budget() -> None:
    """resource_scope.budget_limit allows proposals within the limit."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)
            _, approver_member, _ = await _create_approver(session, org, zone, user)

            zone.resource_scope = {"budget_limit": 5000}
            session.add(zone)
            await session.commit()

            payload = ProposalCreate(
                zone_id=zone.id,
                title="Within budget request",
                proposal_type="resource_allocation",
                payload={"budget_amount": 3000},
            )
            proposal = await create_proposal(
                session,
                organization_id=org.id,
                proposer_id=user.id,
                payload=payload,
            )
            assert proposal.status == "pending_review"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_resource_scope_allowed_boards() -> None:
    """resource_scope.allowed_boards blocks boards not in the list."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)

            board_id = uuid4()
            zone.resource_scope = {"allowed_boards": [str(board_id)]}
            session.add(zone)
            await session.commit()

            # Allowed board
            allowed, reason = check_resource_scope(zone, {"board_id": str(board_id)})
            assert allowed is True

            # Disallowed board
            allowed, reason = check_resource_scope(zone, {"board_id": str(uuid4())})
            assert allowed is False
            assert "allowed_boards" in reason
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 9: Reputation feedback — build_candidates includes accuracy/rate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_candidates_includes_review_metrics() -> None:
    """build_candidates computes review_accuracy and response_rate from feedback."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)
            _, approver_member, _ = await _create_approver(session, org, zone, user)
            await session.commit()

            # Create feedback entries simulating past reviews
            from app.core.time import utcnow

            for i in range(3):
                fb = GardenerFeedback(
                    proposal_id=uuid4(),
                    reviewer_id=approver_member.id,
                    selected_by="gardener_ai",
                    reviewed_in_time=True if i < 2 else False,  # 2/3 on time
                    decision_overturned=False if i < 2 else True,  # 2/3 accurate
                    work_outcome="approved",
                )
                session.add(fb)
            await session.commit()

            candidates = await build_candidates(
                session, zone=zone, exclude_user_id=user.id,
            )
            assert len(candidates) >= 1

            approver_candidate = next(
                (c for c in candidates if c.member_id == approver_member.id), None
            )
            assert approver_candidate is not None
            assert approver_candidate.review_accuracy is not None
            # 2 out of 3 reviews were not overturned
            assert abs(approver_candidate.review_accuracy - 2 / 3) < 0.01
            assert approver_candidate.response_rate is not None
            # 2 out of 3 reviews were on time
            assert abs(approver_candidate.response_rate - 2 / 3) < 0.01
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 10: Reviewer incentive signals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reviewer_incentive_signals_generated() -> None:
    """Finalizing evaluation generates positive signals for good reviewers."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)
            _, approver_member, _ = await _create_approver(session, org, zone, user)

            # Create executor
            executor_user = User(
                clerk_user_id=f"clerk_{uuid4().hex[:12]}",
                email="executor2@example.com",
            )
            session.add(executor_user)
            await session.flush()

            executor_member = OrganizationMember(
                organization_id=org.id,
                user_id=executor_user.id,
                role="member",
                reputation_score=5.0,
            )
            session.add(executor_member)
            await session.flush()

            # Create proposal and feedback
            proposal = Proposal(
                organization_id=org.id,
                zone_id=zone.id,
                proposer_id=user.id,
                title="Test reviewer signals",
                proposal_type="task_execution",
                status="approved",
            )
            session.add(proposal)
            await session.flush()

            fb = GardenerFeedback(
                proposal_id=proposal.id,
                reviewer_id=approver_member.id,
                selected_by="gardener_ai",
                reviewed_in_time=True,
                decision_overturned=False,
                work_outcome="approved",
            )
            session.add(fb)
            await session.commit()

            # Create evaluation linked to proposal
            eval_payload = EvaluationCreate(
                zone_id=zone.id,
                proposal_id=proposal.id,
                executor_id=executor_member.id,
            )
            evaluation = await create_evaluation(
                session,
                organization_id=org.id,
                creator_id=user.id,
                payload=eval_payload,
            )

            # Generate reviewer incentive signals
            signals = await generate_reviewer_incentive_signals(
                session, evaluation=evaluation,
            )
            assert len(signals) == 1
            assert signals[0].target_id == approver_member.id
            assert signals[0].signal_type == "positive"
            assert signals[0].magnitude == 0.3
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 11: Automated evaluation (rule-based check)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_evaluate_automated_check() -> None:
    """auto_evaluate runs automated_check criteria and submits scores."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)

            # Configure evaluation_criteria on zone
            zone.evaluation_criteria = {
                "criteria": [
                    {
                        "name": "timeliness",
                        "type": "automated_check",
                        "weight": 1.0,
                        "config": {"max_days": 30},
                    },
                ],
            }
            session.add(zone)

            executor_user = User(
                clerk_user_id=f"clerk_{uuid4().hex[:12]}",
                email="autoeval-executor@example.com",
            )
            session.add(executor_user)
            await session.flush()

            executor_member = OrganizationMember(
                organization_id=org.id,
                user_id=executor_user.id,
                role="member",
            )
            session.add(executor_member)
            await session.commit()

            eval_payload = EvaluationCreate(
                zone_id=zone.id,
                executor_id=executor_member.id,
            )
            evaluation = await create_evaluation(
                session,
                organization_id=org.id,
                creator_id=user.id,
                payload=eval_payload,
            )
            assert evaluation.status == "pending"

            # Run auto_evaluate
            scores = await auto_evaluate(session, evaluation, zone)
            assert len(scores) == 1
            assert scores[0].criterion_name == "timeliness"
            assert scores[0].evaluator_id == SYSTEM_EVALUATOR_ID
            assert scores[0].score == 1.0  # just created, well within 30 days

            # Evaluation should transition to in_review
            refreshed = await Evaluation.objects.by_id(evaluation.id).first(session)
            assert refreshed is not None
            assert refreshed.status == "in_review"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_auto_evaluate_no_criteria() -> None:
    """auto_evaluate returns empty list when zone has no evaluation_criteria."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)

            executor_user = User(
                clerk_user_id=f"clerk_{uuid4().hex[:12]}",
                email="noauto@example.com",
            )
            session.add(executor_user)
            await session.flush()

            executor_member = OrganizationMember(
                organization_id=org.id,
                user_id=executor_user.id,
                role="member",
            )
            session.add(executor_member)
            await session.commit()

            eval_payload = EvaluationCreate(
                zone_id=zone.id,
                executor_id=executor_member.id,
            )
            evaluation = await create_evaluation(
                session,
                organization_id=org.id,
                creator_id=user.id,
                payload=eval_payload,
            )

            scores = await auto_evaluate(session, evaluation, zone)
            assert scores == []
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# Test 12: Resource scope with resolve_zone_permission
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_zone_permission_with_resource_context() -> None:
    """resolve_zone_permission blocks when resource_context violates scope."""
    engine = await _make_engine()
    try:
        async with await _make_session(engine) as session:
            org, user, member, zone = await _seed_org_and_zone(session)

            zone.resource_scope = {"budget_limit": 500}
            session.add(zone)
            await session.commit()

            # Without resource_context → permission check proceeds normally
            has_perm = await resolve_zone_permission(
                session, member=member, zone=zone, action="proposal.create",
            )
            assert has_perm is True

            # With resource_context within budget → allowed
            has_perm = await resolve_zone_permission(
                session, member=member, zone=zone, action="proposal.create",
                resource_context={"budget_amount": 100},
            )
            assert has_perm is True

            # With resource_context over budget → blocked
            has_perm = await resolve_zone_permission(
                session, member=member, zone=zone, action="proposal.create",
                resource_context={"budget_amount": 1000},
            )
            assert has_perm is False
    finally:
        await engine.dispose()
