"""Schemas for escalation API payloads."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlmodel import SQLModel

RUNTIME_ANNOTATION_TYPES = (datetime, UUID)


class EscalationCreate(SQLModel):
    """Payload for creating an action escalation from a proposal."""

    reason: str = ""


class GovernanceEscalationCreate(SQLModel):
    """Payload for creating a governance escalation on a zone."""

    reason: str = ""


class CosignPayload(SQLModel):
    """Payload for co-signing a governance escalation."""

    pass


class EscalationCosignerRead(SQLModel):
    """Co-signer entry returned by read endpoints."""

    id: UUID
    escalation_id: UUID
    user_id: UUID
    created_at: datetime


class EscalationRead(SQLModel):
    """Escalation payload returned by read endpoints."""

    id: UUID
    organization_id: UUID
    escalation_type: str
    source_proposal_id: UUID | None = None
    source_zone_id: UUID
    target_zone_id: UUID
    escalator_id: UUID
    reason: str
    status: str
    resulting_proposal_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    cosigners: list[EscalationCosignerRead] = []


# Rebuild forward ref
EscalationRead.model_rebuild()
