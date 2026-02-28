"""Evaluation models for post-completion review and incentive workflows."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field

from app.core.time import utcnow
from app.models.base import QueryModel

RUNTIME_ANNOTATION_TYPES = (datetime,)


class Evaluation(QueryModel, table=True):
    """Post-completion evaluation of a task or proposal execution."""

    __tablename__ = "evaluations"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    zone_id: UUID = Field(foreign_key="trust_zones.id", index=True)
    organization_id: UUID = Field(foreign_key="organizations.id", index=True)
    task_id: UUID | None = Field(default=None, index=True)
    proposal_id: UUID | None = Field(
        default=None, foreign_key="proposals.id", index=True
    )
    executor_id: UUID = Field(foreign_key="users.id", index=True)
    status: str = Field(default="pending", index=True)  # pending | in_review | completed
    aggregate_result: dict[str, object] | None = Field(
        default=None, sa_column=Column(JSON)
    )
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class EvaluationScore(QueryModel, table=True):
    """Individual evaluator score for a specific criterion."""

    __tablename__ = "evaluation_scores"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "evaluation_id",
            "evaluator_id",
            "criterion_name",
            name="uq_evaluation_score",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    evaluation_id: UUID = Field(foreign_key="evaluations.id", index=True)
    evaluator_id: UUID = Field(index=True)
    criterion_name: str
    criterion_weight: float = Field(default=1.0)
    score: float
    rationale: str = Field(default="")
    created_at: datetime = Field(default_factory=utcnow)


class IncentiveSignal(QueryModel, table=True):
    """Incentive signal generated from evaluation results."""

    __tablename__ = "incentive_signals"  # pyright: ignore[reportAssignmentType]

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    evaluation_id: UUID = Field(foreign_key="evaluations.id", index=True)
    target_id: UUID = Field(index=True)
    signal_type: str = Field(index=True)  # positive | negative | neutral
    magnitude: float = Field(default=1.0)
    reason: str = Field(default="")
    applied: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
