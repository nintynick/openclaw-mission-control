"""Proposal model for zone-scoped approval workflows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Proposal(QueryModel, table=True):
    """Zone-scoped proposal requiring approval through a decision model."""

    __tablename__ = "proposals"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    zone_id: UUID = Field(foreign_key="trust_zones.id", index=True)
    proposer_id: UUID = Field(foreign_key="users.id", index=True)
    title: str
    description: str = Field(default="")
    proposal_type: str = Field(index=True)
    payload: dict[str, object] | None = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="pending_review", index=True)
    decision_model_override: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    legacy_approval_id: UUID | None = Field(
        default=None, foreign_key="approvals.id", index=True
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    resolved_at: datetime | None = None
