"""Approval request model for individual reviewer decisions on proposals."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class ApprovalRequest(QueryModel, table=True):
    """Individual reviewer decision record for a proposal."""

    __tablename__ = "approval_requests"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    proposal_id: UUID = Field(foreign_key="proposals.id", index=True)
    reviewer_id: UUID = Field(index=True)
    reviewer_type: str = Field(default="human")
    selection_reason: str = Field(default="")
    decision: str | None = None
    rationale: str = Field(default="")
    decided_at: datetime | None = None
    deadline: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
