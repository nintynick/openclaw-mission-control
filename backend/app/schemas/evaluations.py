"""Schemas for evaluation API payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class EvaluationCreate(SQLModel):
    """Payload for creating a new evaluation."""

    zone_id: UUID
    task_id: UUID | None = None
    proposal_id: UUID | None = None
    executor_id: UUID


class EvaluationScoreCreate(SQLModel):
    """Payload for submitting an evaluation score."""

    criterion_name: str
    criterion_weight: float = 1.0
    score: float
    rationale: str = ""


class IncentiveSignalRead(SQLModel):
    """Incentive signal returned by read endpoints."""

    id: UUID
    evaluation_id: UUID
    target_id: UUID
    signal_type: str
    magnitude: float
    reason: str
    applied: bool
    created_at: datetime


class EvaluationScoreRead(SQLModel):
    """Evaluation score returned by read endpoints."""

    id: UUID
    evaluation_id: UUID
    evaluator_id: UUID
    criterion_name: str
    criterion_weight: float
    score: float
    rationale: str
    created_at: datetime


class EvaluationRead(SQLModel):
    """Evaluation payload returned by read endpoints."""

    id: UUID
    zone_id: UUID
    organization_id: UUID
    task_id: UUID | None = None
    proposal_id: UUID | None = None
    executor_id: UUID
    status: str
    aggregate_result: dict[str, object] | None = None
    created_at: datetime
    updated_at: datetime
    scores: list[EvaluationScoreRead] = []
    incentive_signals: list[IncentiveSignalRead] = []


class AutoEvaluateResponse(SQLModel):
    """Response for the auto-evaluate endpoint."""

    scores: list[EvaluationScoreRead] = []
    auto_criteria_count: int = 0


# Rebuild forward refs
EvaluationRead.model_rebuild()
AutoEvaluateResponse.model_rebuild()
