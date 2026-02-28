"""Schemas for trust zone, zone assignment, and audit API payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import Field, SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


# --- JSON blob validation schemas ---


class ResourceScopeConfig(SQLModel):
    """Pydantic validation for the resource_scope JSON column."""

    allowed_boards: list[str] = Field(default_factory=list)
    allowed_agent_types: list[str] = Field(default_factory=list)
    budget_limit: float | None = None


class ConstraintSetConfig(SQLModel):
    """Pydantic validation for the constraints JSON column."""

    blocked_actions: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    max_concurrent_tasks: int | None = None
    require_human_review: bool = False


class DecisionModelConfig(SQLModel):
    """Pydantic validation for the decision_model JSON column."""

    model_type: str = "threshold"
    threshold: int | None = None
    timeout_hours: int | None = None
    fallback_model: str | None = None
    static_reviewers: list[str] = Field(default_factory=list)


# --- Trust Zone CRUD schemas ---


class TrustZoneCreate(SQLModel):
    """Payload for creating a new trust zone."""

    name: str
    slug: str | None = None
    description: str = ""
    parent_zone_id: UUID | None = None
    status: str = "draft"
    responsibilities: dict[str, object] | None = None
    resource_scope: dict[str, object] | None = None
    agent_qualifications: dict[str, object] | None = None
    alignment_requirements: dict[str, object] | None = None
    incentive_model: dict[str, object] | None = None
    constraints: dict[str, object] | None = None
    decision_model: dict[str, object] | None = None
    approval_policy: dict[str, object] | None = None
    escalation_policy: dict[str, object] | None = None
    evaluation_criteria: dict[str, object] | None = None


class TrustZoneUpdate(SQLModel):
    """Payload for updating a trust zone."""

    name: str | None = None
    description: str | None = None
    status: str | None = None
    responsibilities: dict[str, object] | None = None
    resource_scope: dict[str, object] | None = None
    agent_qualifications: dict[str, object] | None = None
    alignment_requirements: dict[str, object] | None = None
    incentive_model: dict[str, object] | None = None
    constraints: dict[str, object] | None = None
    decision_model: dict[str, object] | None = None
    approval_policy: dict[str, object] | None = None
    escalation_policy: dict[str, object] | None = None
    evaluation_criteria: dict[str, object] | None = None


class TrustZoneRead(SQLModel):
    """Trust zone payload returned by read endpoints."""

    id: UUID
    organization_id: UUID
    parent_zone_id: UUID | None = None
    name: str
    slug: str
    description: str
    status: str
    created_by: UUID
    responsibilities: dict[str, object] | None = None
    resource_scope: dict[str, object] | None = None
    agent_qualifications: dict[str, object] | None = None
    alignment_requirements: dict[str, object] | None = None
    incentive_model: dict[str, object] | None = None
    constraints: dict[str, object] | None = None
    decision_model: dict[str, object] | None = None
    approval_policy: dict[str, object] | None = None
    escalation_policy: dict[str, object] | None = None
    evaluation_criteria: dict[str, object] | None = None
    created_at: datetime
    updated_at: datetime


# --- Zone Assignment schemas ---


class ZoneAssignmentCreate(SQLModel):
    """Payload for assigning a member to a zone role."""

    member_id: UUID
    role: str


class ZoneAssignmentRead(SQLModel):
    """Zone assignment payload returned by read endpoints."""

    id: UUID
    zone_id: UUID
    member_id: UUID
    role: str
    assigned_by: UUID
    created_at: datetime
    updated_at: datetime


# --- Audit Entry schemas ---


class AuditEntryRead(SQLModel):
    """Audit entry payload returned by read endpoints."""

    id: UUID
    organization_id: UUID
    zone_id: UUID | None = None
    actor_id: UUID
    actor_type: str
    action: str
    target_type: str
    target_id: UUID | None = None
    payload: dict[str, object] | None = None
    created_at: datetime
