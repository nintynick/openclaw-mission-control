"""Audit query endpoint for governance audit trail."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel import col

from app.api.deps import require_org_member
from app.db.session import get_session
from app.models.audit_entries import AuditEntry
from app.schemas.audit import AuditEntryRead
from app.services.organizations import OrganizationContext

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

router = APIRouter(prefix="/organizations/me/audit", tags=["audit"])
SESSION_DEP = Depends(get_session)
ORG_MEMBER_DEP = Depends(require_org_member)


@router.get("", response_model=list[AuditEntryRead])
async def list_audit_entries(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
    zone_id: UUID | None = None,
    action: str | None = None,
    actor_id: UUID | None = None,
    actor_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AuditEntryRead]:
    """Query audit entries for the active organization."""
    query = AuditEntry.objects.filter_by(organization_id=ctx.organization.id)
    if zone_id is not None:
        query = query.filter_by(zone_id=zone_id)
    if action is not None:
        query = query.filter(col(AuditEntry.action) == action)
    if actor_id is not None:
        query = query.filter(col(AuditEntry.actor_id) == actor_id)
    if actor_type is not None:
        query = query.filter(col(AuditEntry.actor_type) == actor_type)

    entries = await query.order_by(
        col(AuditEntry.created_at).desc()
    ).offset(offset).limit(limit).all(session)

    return [AuditEntryRead.model_validate(e, from_attributes=True) for e in entries]
