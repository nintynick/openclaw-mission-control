"""Escalation models for action and governance escalation workflows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Escalation(QueryModel, table=True):
    """Escalation record for action or governance disputes."""

    __tablename__ = "escalations"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    escalation_type: str = Field(index=True)  # action | governance
    source_proposal_id: UUID | None = Field(
        default=None, foreign_key="proposals.id", index=True
    )
    source_zone_id: UUID = Field(foreign_key="trust_zones.id", index=True)
    target_zone_id: UUID = Field(foreign_key="trust_zones.id", index=True)
    escalator_id: UUID = Field(foreign_key="users.id", index=True)
    reason: str = Field(default="")
    status: str = Field(default="pending", index=True)  # pending | accepted | dismissed | resolved
    resulting_proposal_id: UUID | None = Field(
        default=None, foreign_key="proposals.id", index=True
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class EscalationCosigner(QueryModel, table=True):
    """Co-signer for governance escalations requiring multiple endorsers."""

    __tablename__ = "escalation_cosigners"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint("escalation_id", "user_id", name="uq_escalation_cosigner"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    escalation_id: UUID = Field(foreign_key="escalations.id", index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
