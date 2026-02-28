# ruff: noqa

"""Tests for the pending-reviews API endpoint."""

from __future__ import annotations

from uuid import uuid4

from app.models.approval_requests import ApprovalRequest
from app.models.proposals import Proposal


def test_approval_request_decision_default_none() -> None:
    """ApprovalRequest.decision defaults to None (undecided)."""
    req = ApprovalRequest(
        proposal_id=uuid4(),
        reviewer_id=uuid4(),
    )
    assert req.decision is None
    assert req.deadline is None


def test_proposal_with_risk_level() -> None:
    """Proposals can carry risk_level and conflicts_detected."""
    proposal = Proposal(
        organization_id=uuid4(),
        zone_id=uuid4(),
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
        risk_level="high",
        conflicts_detected=[{"conflict_type": "self_review", "reviewer_id": str(uuid4())}],
    )
    assert proposal.risk_level == "high"
    assert isinstance(proposal.conflicts_detected, list)
    assert len(proposal.conflicts_detected) == 1
