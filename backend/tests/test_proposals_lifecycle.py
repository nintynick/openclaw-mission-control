# ruff: noqa

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.proposals import Proposal
from app.models.trust_zones import TrustZone
from app.services.approval_engine import VALID_PROPOSAL_TYPES, check_auto_approve


def test_valid_proposal_types() -> None:
    assert "task_execution" in VALID_PROPOSAL_TYPES
    assert "resource_allocation" in VALID_PROPOSAL_TYPES
    assert "zone_change" in VALID_PROPOSAL_TYPES
    assert "membership_change" in VALID_PROPOSAL_TYPES


def test_check_auto_approve_no_policy() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="z",
        slug="z",
        created_by=uuid4(),
        approval_policy=None,
    )
    proposal = Proposal(
        organization_id=uuid4(),
        zone_id=zone.id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
    )
    assert check_auto_approve(zone=zone, proposal=proposal) is False


def test_check_auto_approve_with_matching_type() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="z",
        slug="z",
        created_by=uuid4(),
        approval_policy={"auto_approve_types": ["task_execution"]},
    )
    proposal = Proposal(
        organization_id=uuid4(),
        zone_id=zone.id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="task_execution",
    )
    assert check_auto_approve(zone=zone, proposal=proposal) is True


def test_check_auto_approve_non_matching_type() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="z",
        slug="z",
        created_by=uuid4(),
        approval_policy={"auto_approve_types": ["task_execution"]},
    )
    proposal = Proposal(
        organization_id=uuid4(),
        zone_id=zone.id,
        proposer_id=uuid4(),
        title="Test",
        proposal_type="zone_change",
    )
    assert check_auto_approve(zone=zone, proposal=proposal) is False


def test_proposal_model_defaults() -> None:
    proposal = Proposal(
        organization_id=uuid4(),
        zone_id=uuid4(),
        proposer_id=uuid4(),
        title="Test Proposal",
        proposal_type="task_execution",
    )
    assert proposal.status == "pending_review"
    assert proposal.description == ""
    assert proposal.payload is None
    assert proposal.legacy_approval_id is None
    assert proposal.resolved_at is None
