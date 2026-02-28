# ruff: noqa

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.proposals import Proposal
from app.services.approval_engine import detect_conflicts


def _make_proposal(proposer_id=None, member_id=None) -> Proposal:
    pid = proposer_id or uuid4()
    payload = {"member_id": str(member_id)} if member_id else None
    return Proposal(
        organization_id=uuid4(),
        zone_id=uuid4(),
        proposer_id=pid,
        title="Test",
        proposal_type="membership_change",
        payload=payload,
    )


def test_no_conflicts_when_no_overlap() -> None:
    proposal = _make_proposal()
    reviewer1, reviewer2 = uuid4(), uuid4()
    conflicts = detect_conflicts(proposal=proposal, reviewer_ids=[reviewer1, reviewer2])
    assert conflicts == []


def test_self_review_conflict_detected() -> None:
    proposer = uuid4()
    proposal = _make_proposal(proposer_id=proposer)
    conflicts = detect_conflicts(proposal=proposal, reviewer_ids=[proposer])
    assert len(conflicts) == 1
    assert conflicts[0]["conflict_type"] == "self_review"


def test_subject_of_proposal_conflict_detected() -> None:
    member = uuid4()
    proposal = _make_proposal(member_id=member)
    conflicts = detect_conflicts(proposal=proposal, reviewer_ids=[member])
    assert len(conflicts) == 1
    assert conflicts[0]["conflict_type"] == "subject_of_proposal"


def test_both_self_review_and_subject_conflict() -> None:
    member = uuid4()
    proposal = _make_proposal(proposer_id=member, member_id=member)
    conflicts = detect_conflicts(proposal=proposal, reviewer_ids=[member])
    assert len(conflicts) == 2
    types = {c["conflict_type"] for c in conflicts}
    assert "self_review" in types
    assert "subject_of_proposal" in types


def test_mixed_reviewers_partial_conflicts() -> None:
    proposer = uuid4()
    clean_reviewer = uuid4()
    proposal = _make_proposal(proposer_id=proposer)
    conflicts = detect_conflicts(proposal=proposal, reviewer_ids=[proposer, clean_reviewer])
    assert len(conflicts) == 1
    assert conflicts[0]["reviewer_id"] == str(proposer)
