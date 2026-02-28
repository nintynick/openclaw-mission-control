"""Gardener feedback model for tracking LLM reviewer selection outcomes."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class GardenerFeedback(QueryModel, table=True):
    """Tracks reviewer selection quality and outcomes for the gardener feedback loop."""

    __tablename__ = "gardener_feedback"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    proposal_id: UUID = Field(foreign_key="proposals.id", index=True)
    reviewer_id: UUID = Field(index=True)
    selected_by: str = Field(index=True)  # rule_based | gardener_ai
    reviewed_in_time: bool | None = None
    decision_overturned: bool | None = None
    work_outcome: str | None = None  # positive | negative | neutral
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
