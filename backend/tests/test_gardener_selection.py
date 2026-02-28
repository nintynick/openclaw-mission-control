# ruff: noqa

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.gardener_feedback import GardenerFeedback
from app.services.gardener import (
    GardenerService,
    ReviewerCandidate,
    ReviewerSelection,
)


def test_gardener_feedback_model_defaults() -> None:
    fb = GardenerFeedback(
        proposal_id=uuid4(),
        reviewer_id=uuid4(),
        selected_by="rule_based",
    )
    assert fb.id is not None
    assert fb.reviewed_in_time is None
    assert fb.decision_overturned is None
    assert fb.work_outcome is None
    assert fb.created_at is not None
    assert fb.updated_at is not None


def test_gardener_feedback_selected_by_values() -> None:
    for method in ("rule_based", "gardener_ai"):
        fb = GardenerFeedback(
            proposal_id=uuid4(),
            reviewer_id=uuid4(),
            selected_by=method,
        )
        assert fb.selected_by == method


def test_rule_based_fallback_prefers_approvers() -> None:
    approver = ReviewerCandidate(
        member_id=uuid4(),
        role="approver",
        reputation_score=5.0,
        past_review_count=10,
    )
    gardener = ReviewerCandidate(
        member_id=uuid4(),
        role="gardener",
        reputation_score=8.0,
        past_review_count=20,
    )
    evaluator = ReviewerCandidate(
        member_id=uuid4(),
        role="evaluator",
        reputation_score=3.0,
        past_review_count=5,
    )

    selections = GardenerService._rule_based_fallback(
        [evaluator, gardener, approver],
        max_reviewers=2,
    )

    assert len(selections) == 2
    # Approver should be first due to role preference
    assert selections[0].reviewer_id == approver.member_id
    assert selections[1].reviewer_id == gardener.member_id


def test_rule_based_fallback_respects_max_reviewers() -> None:
    candidates = [
        ReviewerCandidate(
            member_id=uuid4(),
            role="approver",
            reputation_score=float(i),
        )
        for i in range(5)
    ]

    selections = GardenerService._rule_based_fallback(candidates, max_reviewers=3)
    assert len(selections) == 3


def test_rule_based_fallback_empty_candidates() -> None:
    selections = GardenerService._rule_based_fallback([], max_reviewers=3)
    assert selections == []


def test_rule_based_fallback_sorts_by_reputation() -> None:
    c1 = ReviewerCandidate(
        member_id=uuid4(),
        role="approver",
        reputation_score=3.0,
        past_review_count=5,
    )
    c2 = ReviewerCandidate(
        member_id=uuid4(),
        role="approver",
        reputation_score=8.0,
        past_review_count=2,
    )

    selections = GardenerService._rule_based_fallback([c1, c2], max_reviewers=2)
    # Higher reputation should come first (both are approvers)
    assert selections[0].reviewer_id == c2.member_id
    assert selections[1].reviewer_id == c1.member_id


def test_reviewer_selection_dataclass() -> None:
    rid = uuid4()
    selection = ReviewerSelection(reviewer_id=rid, reason="test reason")
    assert selection.reviewer_id == rid
    assert selection.reason == "test reason"


def test_reviewer_candidate_defaults() -> None:
    mid = uuid4()
    candidate = ReviewerCandidate(member_id=mid, role="approver")
    assert candidate.zone_assignments == []
    assert candidate.reputation_score == 0.0
    assert candidate.past_review_count == 0
    assert candidate.avg_response_time_hours is None


def test_gardener_service_init_default_model() -> None:
    service = GardenerService()
    assert service._model == "claude-sonnet-4-20250514"


def test_gardener_service_init_custom_model() -> None:
    service = GardenerService(model="claude-opus-4-20250514")
    assert service._model == "claude-opus-4-20250514"
