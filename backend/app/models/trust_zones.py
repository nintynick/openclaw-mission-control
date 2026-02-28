"""Trust zone model for hierarchical governance delegation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class TrustZone(QueryModel, table=True):
    """Hierarchical governance zone scoping delegation, constraints, and policy."""

    __tablename__ = "trust_zones"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    parent_zone_id: UUID | None = Field(
        default=None,
        foreign_key="trust_zones.id",
        index=True,
    )
    name: str
    slug: str = Field(index=True)
    description: str = Field(default="")
    status: str = Field(default="draft", index=True)
    created_by: UUID = Field(foreign_key="users.id", index=True)

    # Seven governance parameters stored as JSON
    responsibilities: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    resource_scope: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    agent_qualifications: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    alignment_requirements: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    incentive_model: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    constraints: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    decision_model: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )

    # Governance hooks (populated in later phases)
    approval_policy: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    escalation_policy: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    evaluation_criteria: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
