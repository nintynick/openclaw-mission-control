# ruff: noqa

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from app.models.audit_entries import AuditEntry
from app.services.audit import record_audit


@dataclass
class _FakeSession:
    added: list[Any] = field(default_factory=list)
    committed: int = 0
    refreshed: list[Any] = field(default_factory=list)

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.committed += 1

    async def refresh(self, value: Any) -> None:
        self.refreshed.append(value)


@pytest.mark.asyncio
async def test_record_audit_creates_entry() -> None:
    session = _FakeSession()
    org_id = uuid4()
    actor_id = uuid4()
    zone_id = uuid4()

    entry = await record_audit(
        session,
        organization_id=org_id,
        actor_id=actor_id,
        actor_type="human",
        action="zone.create",
        zone_id=zone_id,
        target_type="trust_zone",
        target_id=zone_id,
        payload={"key": "value"},
    )

    assert isinstance(entry, AuditEntry)
    assert entry.organization_id == org_id
    assert entry.actor_id == actor_id
    assert entry.actor_type == "human"
    assert entry.action == "zone.create"
    assert entry.zone_id == zone_id
    assert entry.target_type == "trust_zone"
    assert entry.target_id == zone_id
    assert entry.payload == {"key": "value"}
    assert session.committed == 1
    assert len(session.refreshed) == 1


@pytest.mark.asyncio
async def test_record_audit_no_commit_when_disabled() -> None:
    session = _FakeSession()
    entry = await record_audit(
        session,
        organization_id=uuid4(),
        actor_id=uuid4(),
        actor_type="system",
        action="test.action",
        commit=False,
    )

    assert isinstance(entry, AuditEntry)
    assert session.committed == 0
    assert len(session.refreshed) == 0
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_record_audit_defaults() -> None:
    session = _FakeSession()
    entry = await record_audit(
        session,
        organization_id=uuid4(),
        actor_id=uuid4(),
        actor_type="ai_agent",
        action="proposal.approve",
    )

    assert entry.zone_id is None
    assert entry.target_type == ""
    assert entry.target_id is None
    assert entry.payload is None


def test_audit_entry_model_has_no_updated_at() -> None:
    """Audit entries are append-only and should not have updated_at."""
    entry = AuditEntry(
        organization_id=uuid4(),
        actor_id=uuid4(),
        actor_type="human",
        action="test",
    )
    assert not hasattr(entry, "updated_at") or "updated_at" not in AuditEntry.model_fields
