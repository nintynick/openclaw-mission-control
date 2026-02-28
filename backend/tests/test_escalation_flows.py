# ruff: noqa

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from app.models.escalations import Escalation, EscalationCosigner
from app.models.proposals import Proposal
from app.models.trust_zones import TrustZone
from app.services.escalation_engine import _get_cosigner_threshold


def test_escalation_model_defaults() -> None:
    esc = Escalation(
        organization_id=uuid4(),
        escalation_type="action",
        source_zone_id=uuid4(),
        target_zone_id=uuid4(),
        escalator_id=uuid4(),
    )
    assert esc.status == "pending"
    assert esc.reason == ""
    assert esc.source_proposal_id is None
    assert esc.resulting_proposal_id is None
    assert esc.created_at is not None
    assert esc.updated_at is not None


def test_escalation_type_values() -> None:
    for etype in ("action", "governance"):
        esc = Escalation(
            organization_id=uuid4(),
            escalation_type=etype,
            source_zone_id=uuid4(),
            target_zone_id=uuid4(),
            escalator_id=uuid4(),
        )
        assert esc.escalation_type == etype


def test_cosigner_model_defaults() -> None:
    cosigner = EscalationCosigner(
        escalation_id=uuid4(),
        user_id=uuid4(),
    )
    assert cosigner.id is not None
    assert cosigner.created_at is not None


def test_get_cosigner_threshold_default() -> None:
    assert _get_cosigner_threshold(None) == 2


def test_get_cosigner_threshold_from_policy() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy={"cosigner_threshold": 3},
    )
    assert _get_cosigner_threshold(zone) == 3


def test_get_cosigner_threshold_minimum_one() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy={"cosigner_threshold": 0},
    )
    assert _get_cosigner_threshold(zone) == 1


def test_get_cosigner_threshold_no_policy() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy=None,
    )
    assert _get_cosigner_threshold(zone) == 2


def test_get_cosigner_threshold_invalid_type() -> None:
    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy={"cosigner_threshold": "three"},
    )
    assert _get_cosigner_threshold(zone) == 2
