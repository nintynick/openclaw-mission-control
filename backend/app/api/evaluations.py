"""Evaluation management endpoints for post-completion review workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import col

from app.api.deps import require_org_member
from app.core.auth import get_auth_context
from app.db.session import get_session
from app.models.evaluations import Evaluation, EvaluationScore, IncentiveSignal
from app.models.trust_zones import TrustZone
from app.schemas.evaluations import (
    AutoEvaluateResponse,
    EvaluationCreate,
    EvaluationRead,
    EvaluationScoreCreate,
    EvaluationScoreRead,
    IncentiveSignalRead,
)
from app.services.evaluations import (
    apply_incentive_signals,
    auto_evaluate,
    create_evaluation,
    finalize_evaluation,
    submit_score,
)
from app.services.audit import record_audit
from app.services.organizations import OrganizationContext
from app.services.permission_resolver import resolve_zone_permission

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.core.auth import AuthContext

router = APIRouter(prefix="/organizations/me/evaluations", tags=["evaluations"])
SESSION_DEP = Depends(get_session)
AUTH_DEP = Depends(get_auth_context)
ORG_MEMBER_DEP = Depends(require_org_member)


async def _check_zone_perm(
    session: AsyncSession,
    member: object,
    zone_id: UUID,
    action: str,
) -> None:
    """Load zone and check permission, raising 403 on failure."""
    from app.models.organization_members import OrganizationMember

    zone = await TrustZone.objects.by_id(zone_id).first(session)
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
    if not isinstance(member, OrganizationMember):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    allowed = await resolve_zone_permission(
        session, member=member, zone=zone, action=action,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {action}",
        )


async def _get_evaluation_or_404(
    session: AsyncSession,
    *,
    evaluation_id: UUID,
    organization_id: UUID,
) -> Evaluation:
    evaluation = await Evaluation.objects.by_id(evaluation_id).first(session)
    if evaluation is None or evaluation.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return evaluation


def _evaluation_to_read(
    evaluation: Evaluation,
    scores: list[EvaluationScore] | None = None,
    signals: list[IncentiveSignal] | None = None,
) -> EvaluationRead:
    model = EvaluationRead.model_validate(evaluation, from_attributes=True)
    if scores is not None:
        model.scores = [
            EvaluationScoreRead.model_validate(s, from_attributes=True) for s in scores
        ]
    if signals is not None:
        model.incentive_signals = [
            IncentiveSignalRead.model_validate(s, from_attributes=True)
            for s in signals
        ]
    return model


@router.post("", response_model=EvaluationRead)
async def create_evaluation_endpoint(
    payload: EvaluationCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> EvaluationRead:
    """Create a new evaluation for a completed task or proposal."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    await _check_zone_perm(session, ctx.member, payload.zone_id, "evaluation.create")

    evaluation = await create_evaluation(
        session,
        organization_id=ctx.organization.id,
        creator_id=auth.user.id,
        payload=payload,
    )
    return _evaluation_to_read(evaluation)


@router.get("", response_model=list[EvaluationRead])
async def list_evaluations(
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
    zone_id: UUID | None = None,
    evaluation_status: str | None = None,
) -> list[EvaluationRead]:
    """List evaluations in the active organization."""
    query = Evaluation.objects.filter_by(organization_id=ctx.organization.id)
    if zone_id is not None:
        query = query.filter_by(zone_id=zone_id)
    if evaluation_status is not None:
        query = query.filter(col(Evaluation.status) == evaluation_status)
    evaluations = await query.order_by(col(Evaluation.created_at).desc()).all(session)
    return [_evaluation_to_read(e) for e in evaluations]


@router.get("/{evaluation_id}", response_model=EvaluationRead)
async def get_evaluation(
    evaluation_id: UUID,
    session: AsyncSession = SESSION_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> EvaluationRead:
    """Get evaluation detail with scores and incentive signals."""
    evaluation = await _get_evaluation_or_404(
        session,
        evaluation_id=evaluation_id,
        organization_id=ctx.organization.id,
    )
    scores = await EvaluationScore.objects.filter_by(
        evaluation_id=evaluation.id,
    ).all(session)
    signals = await IncentiveSignal.objects.filter_by(
        evaluation_id=evaluation.id,
    ).all(session)
    return _evaluation_to_read(evaluation, scores, signals)


@router.post("/{evaluation_id}/scores", response_model=EvaluationScoreRead)
async def submit_evaluation_score(
    evaluation_id: UUID,
    payload: EvaluationScoreCreate,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> EvaluationScoreRead:
    """Submit a score for a specific evaluation criterion."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    evaluation = await _get_evaluation_or_404(
        session,
        evaluation_id=evaluation_id,
        organization_id=ctx.organization.id,
    )

    await _check_zone_perm(session, ctx.member, evaluation.zone_id, "evaluation.submit")

    score = await submit_score(
        session,
        evaluation=evaluation,
        evaluator_id=ctx.member.id,
        payload=payload,
    )

    await record_audit(
        session,
        organization_id=ctx.organization.id,
        actor_id=auth.user.id,
        actor_type="human",
        action="evaluation.score",
        zone_id=evaluation.zone_id,
        target_type="evaluation",
        target_id=evaluation.id,
    )

    return EvaluationScoreRead.model_validate(score, from_attributes=True)


@router.post("/{evaluation_id}/finalize", response_model=EvaluationRead)
async def finalize_evaluation_endpoint(
    evaluation_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> EvaluationRead:
    """Finalize an evaluation: aggregate scores and apply incentive signals."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    evaluation = await _get_evaluation_or_404(
        session,
        evaluation_id=evaluation_id,
        organization_id=ctx.organization.id,
    )

    await _check_zone_perm(session, ctx.member, evaluation.zone_id, "evaluation.submit")

    evaluation = await finalize_evaluation(
        session,
        evaluation=evaluation,
        finalized_by=auth.user.id,
    )

    # Apply incentive signals to reputation scores
    await apply_incentive_signals(session, evaluation=evaluation)

    scores = await EvaluationScore.objects.filter_by(
        evaluation_id=evaluation.id,
    ).all(session)
    signals = await IncentiveSignal.objects.filter_by(
        evaluation_id=evaluation.id,
    ).all(session)

    return _evaluation_to_read(evaluation, scores, signals)


@router.post("/{evaluation_id}/auto-evaluate", response_model=AutoEvaluateResponse)
async def auto_evaluate_endpoint(
    evaluation_id: UUID,
    session: AsyncSession = SESSION_DEP,
    auth: AuthContext = AUTH_DEP,
    ctx: OrganizationContext = ORG_MEMBER_DEP,
) -> AutoEvaluateResponse:
    """Run automated evaluation criteria (rule-based and LLM) on an evaluation."""
    if auth.user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    evaluation = await _get_evaluation_or_404(
        session,
        evaluation_id=evaluation_id,
        organization_id=ctx.organization.id,
    )

    await _check_zone_perm(session, ctx.member, evaluation.zone_id, "evaluation.submit")

    zone = await TrustZone.objects.by_id(evaluation.zone_id).first(session)
    if zone is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")

    scores = await auto_evaluate(session, evaluation, zone)

    criteria_config = zone.evaluation_criteria
    auto_criteria_count = 0
    if isinstance(criteria_config, dict):
        criteria_list = criteria_config.get("criteria", [])
        if isinstance(criteria_list, list):
            auto_criteria_count = len(criteria_list)

    return AutoEvaluateResponse(
        scores=[
            EvaluationScoreRead.model_validate(s, from_attributes=True) for s in scores
        ],
        auto_criteria_count=auto_criteria_count,
    )
