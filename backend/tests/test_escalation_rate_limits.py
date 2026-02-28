# ruff: noqa

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.core.time import utcnow
from app.models.escalations import Escalation
from app.models.trust_zones import TrustZone
from app.services.escalation_engine import _check_rate_limit


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
async def test_rate_limit_no_policy() -> None:
    """No policy means no rate limit — should not raise."""
    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy=None,
    )
    session = _FakeSession()
    # Should complete without error
    await _check_rate_limit(session, escalator_id=uuid4(), zone=zone)


@pytest.mark.asyncio
async def test_rate_limit_no_max_key() -> None:
    """Policy exists but no max_escalations_per_day — should not raise."""
    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy={"cosigner_threshold": 2},
    )
    session = _FakeSession()
    await _check_rate_limit(session, escalator_id=uuid4(), zone=zone)


@pytest.mark.asyncio
async def test_rate_limit_under_threshold() -> None:
    """Under the rate limit — should not raise."""
    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy={"max_escalations_per_day": 3},
    )
    # Return 2 recent escalations (under limit of 3)
    recent = [
        Escalation(
            organization_id=zone.organization_id,
            escalation_type="action",
            source_zone_id=zone.id,
            target_zone_id=uuid4(),
            escalator_id=uuid4(),
        )
        for _ in range(2)
    ]
    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=recent),
    ])
    await _check_rate_limit(session, escalator_id=uuid4(), zone=zone)


@pytest.mark.asyncio
async def test_rate_limit_at_threshold_raises() -> None:
    """At the rate limit — should raise 429."""
    from fastapi import HTTPException

    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy={"max_escalations_per_day": 2},
    )
    recent = [
        Escalation(
            organization_id=zone.organization_id,
            escalation_type="action",
            source_zone_id=zone.id,
            target_zone_id=uuid4(),
            escalator_id=uuid4(),
        )
        for _ in range(2)
    ]
    session = _FakeSession(exec_results=[
        _FakeExecResult(all_values=recent),
    ])
    with pytest.raises(HTTPException) as exc_info:
        await _check_rate_limit(session, escalator_id=uuid4(), zone=zone)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_rate_limit_invalid_max_type() -> None:
    """Non-integer max_escalations_per_day — should not raise."""
    zone = TrustZone(
        organization_id=uuid4(),
        name="test",
        slug="test",
        created_by=uuid4(),
        escalation_policy={"max_escalations_per_day": "unlimited"},
    )
    session = _FakeSession()
    await _check_rate_limit(session, escalator_id=uuid4(), zone=zone)
