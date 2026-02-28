"""Schemas for proposal and approval request API payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class ProposalCreate(SQLModel):
    """Payload for creating a new proposal."""

    zone_id: UUID
    title: str
    description: str = ""
    proposal_type: str
    payload: dict[str, object] | None = None
    decision_model_override: dict[str, object] | None = None
    expires_at: datetime | None = None


class ProposalRead(SQLModel):
    """Proposal payload returned by read endpoints."""

    id: UUID
    organization_id: UUID
    zone_id: UUID
    proposer_id: UUID
    title: str
    description: str
    proposal_type: str
    payload: dict[str, object] | None = None
    status: str
    risk_level: str | None = None
    conflicts_detected: list[dict[str, object]] | None = None
    decision_model_override: dict[str, object] | None = None
    legacy_approval_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
    approval_requests: list[ApprovalRequestRead] = []


class ApprovalRequestRead(SQLModel):
    """Approval request payload returned by read endpoints."""

    id: UUID
    proposal_id: UUID
    reviewer_id: UUID
    reviewer_type: str
    selection_reason: str
    decision: str | None = None
    rationale: str
    decided_at: datetime | None = None
    deadline: datetime | None = None
    created_at: datetime


class VotePayload(SQLModel):
    """Payload for casting a vote on a proposal."""

    rationale: str = ""


# Rebuild forward ref
ProposalRead.model_rebuild()
