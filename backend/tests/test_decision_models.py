# ruff: noqa

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from app.models.approval_requests import ApprovalRequest
from app.models.proposals import Proposal
from app.models.trust_zones import TrustZone
from app.services.approval_engine import _evaluate_and_resolve


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
    added: list[Any] = field(default_factory=list)
    committed: int = 0

    async def exec(self, _statement: Any) -> Any:
        if not self.exec_results:
            return _FakeExecResult()
        return self.exec_results.pop(0)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed += 1

    async def refresh(self, _value: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_unilateral_first_approve_resolves() -> None:
    zone_id = uuid4()
    proposal = Proposal(
        id=uuid4(),
        organization_id=uuid4(),
        zone_id=zone_id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
        decision_model_override={"model_type": "unilateral"},
    )
    request = ApprovalRequest(
        proposal_id=proposal.id,
        reviewer_id=uuid4(),
        decision="approve",
    )

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[request]),  # all requests for proposal
    ])
    await _evaluate_and_resolve(session, proposal=proposal)
    assert proposal.status == "approved"
    assert proposal.resolved_at is not None


@pytest.mark.asyncio
async def test_threshold_two_of_three() -> None:
    zone_id = uuid4()
    proposal = Proposal(
        id=uuid4(),
        organization_id=uuid4(),
        zone_id=zone_id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
        decision_model_override={"model_type": "threshold", "threshold": 2},
    )
    r1 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="approve")
    r2 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="approve")
    r3 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision=None)

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[r1, r2, r3]),
    ])
    await _evaluate_and_resolve(session, proposal=proposal)
    assert proposal.status == "approved"


@pytest.mark.asyncio
async def test_majority_requires_over_half() -> None:
    zone_id = uuid4()
    proposal = Proposal(
        id=uuid4(),
        organization_id=uuid4(),
        zone_id=zone_id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
        decision_model_override={"model_type": "majority"},
    )
    r1 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="approve")
    r2 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="reject")
    r3 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="reject")

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[r1, r2, r3]),
    ])
    await _evaluate_and_resolve(session, proposal=proposal)
    assert proposal.status == "rejected"


@pytest.mark.asyncio
async def test_consensus_all_approve() -> None:
    zone_id = uuid4()
    proposal = Proposal(
        id=uuid4(),
        organization_id=uuid4(),
        zone_id=zone_id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
        decision_model_override={"model_type": "consensus", "threshold": 1},
    )
    r1 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="approve")
    r2 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="approve")

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[r1, r2]),
    ])
    await _evaluate_and_resolve(session, proposal=proposal)
    assert proposal.status == "approved"


@pytest.mark.asyncio
async def test_consensus_timeout_resolves_with_threshold_fallback() -> None:
    """Gap 13: Consensus model with timeout_hours triggers fallback resolution."""
    from datetime import datetime, timedelta

    zone_id = uuid4()
    created_at = datetime(2020, 1, 1)  # far in the past
    proposal = Proposal(
        id=uuid4(),
        organization_id=uuid4(),
        zone_id=zone_id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
        decision_model_override={
            "model_type": "consensus",
            "threshold": 1,
            "timeout_hours": 1,
        },
        created_at=created_at,
    )
    r1 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="approve")
    r2 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision=None)  # undecided

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[r1, r2]),
    ])
    await _evaluate_and_resolve(session, proposal=proposal)
    # Not all voted, but timeout has expired (created_at is far in the past)
    # With 1 approve >= threshold of 1, should resolve as approved
    assert proposal.status == "approved"
    assert proposal.resolved_at is not None


@pytest.mark.asyncio
async def test_consensus_no_timeout_remains_pending() -> None:
    """Without timeout expiring, consensus model doesn't resolve on partial votes."""
    zone_id = uuid4()
    proposal = Proposal(
        id=uuid4(),
        organization_id=uuid4(),
        zone_id=zone_id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
        decision_model_override={
            "model_type": "consensus",
            "threshold": 1,
            "timeout_hours": 999999,  # Very far in the future
        },
    )
    r1 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="approve")
    r2 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision=None)

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[r1, r2]),
    ])
    await _evaluate_and_resolve(session, proposal=proposal)
    # Timeout not expired yet, still pending
    assert proposal.status == "pending_review"
    assert proposal.resolved_at is None


@pytest.mark.asyncio
async def test_consensus_broken_falls_back_to_threshold() -> None:
    zone_id = uuid4()
    proposal = Proposal(
        id=uuid4(),
        organization_id=uuid4(),
        zone_id=zone_id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
        decision_model_override={"model_type": "consensus", "threshold": 1},
    )
    r1 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="approve")
    r2 = ApprovalRequest(proposal_id=proposal.id, reviewer_id=uuid4(), decision="reject")

    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=[r1, r2]),
    ])
    await _evaluate_and_resolve(session, proposal=proposal)
    assert proposal.status == "approved"  # 1 approve >= threshold of 1
