# ruff: noqa

"""Tests for the audit query API schema."""

from __future__ import annotations

from uuid import uuid4

from app.models.audit_entries import AuditEntry
from app.schemas.audit import AuditEntryRead


def test_audit_entry_model_defaults() -> None:
    entry = AuditEntry(
        organization_id=uuid4(),
        actor_id=uuid4(),
        actor_type="human",
        action="proposal.create",
    )
    assert entry.id is not None
    assert entry.zone_id is None
    assert entry.target_type == ""
    assert entry.target_id is None
    assert entry.payload is None
    assert entry.created_at is not None


def test_audit_entry_read_from_model() -> None:
    entry = AuditEntry(
        organization_id=uuid4(),
        zone_id=uuid4(),
        actor_id=uuid4(),
        actor_type="system",
        action="escalation.auto.timeout",
        target_type="escalation",
        target_id=uuid4(),
        payload={"reason": "timeout"},
    )
    read = AuditEntryRead.model_validate(entry, from_attributes=True)
    assert read.organization_id == entry.organization_id
    assert read.action == "escalation.auto.timeout"
    assert read.actor_type == "system"
    assert read.payload == {"reason": "timeout"}
