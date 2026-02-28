"""Evaluation service for post-completion review, scoring, and incentive signal generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from uuid import UUID

from app.core.logging import get_logger
from app.core.time import utcnow
from app.models.evaluations import Evaluation, EvaluationScore, IncentiveSignal
from app.models.organization_members import OrganizationMember
from app.models.trust_zones import TrustZone
from app.services.audit import record_audit
from app.services.governance_notifications.queue import GovernanceNotification, enqueue_notification

logger = get_logger(__name__)

SYSTEM_EVALUATOR_ID = UUID("00000000-0000-0000-0000-000000000000")

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.schemas.evaluations import EvaluationCreate, EvaluationScoreCreate


async def create_evaluation(
    session: AsyncSession,
    *,
    organization_id: UUID,
    creator_id: UUID,
    payload: EvaluationCreate,
) -> Evaluation:
    """Create a new evaluation for a completed task or proposal."""
    zone = await TrustZone.objects.by_id(payload.zone_id).first(session)
    if zone is None or zone.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Zone not found in organization",
        )

    now = utcnow()
    evaluation = Evaluation(
        zone_id=payload.zone_id,
        organization_id=organization_id,
        task_id=payload.task_id,
        proposal_id=payload.proposal_id,
        executor_id=payload.executor_id,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(evaluation)
    await session.flush()

    await record_audit(
        session,
        organization_id=organization_id,
        actor_id=creator_id,
        actor_type="human",
        action="evaluation.create",
        zone_id=payload.zone_id,
        target_type="evaluation",
        target_id=evaluation.id,
        commit=False,
    )

    await session.commit()
    await session.refresh(evaluation)

    # Notify executor (fire-and-forget)
    try:
        enqueue_notification(GovernanceNotification(
            event_type="evaluation_created",
            organization_id=organization_id,
            zone_id=payload.zone_id,
            target_ids=[payload.executor_id],
            payload={
                "evaluation_id": str(evaluation.id),
            },
        ))
    except Exception:
        logger.warning("Failed to enqueue evaluation_created notification", exc_info=True)

    return evaluation


async def submit_score(
    session: AsyncSession,
    *,
    evaluation: Evaluation,
    evaluator_id: UUID,
    payload: EvaluationScoreCreate,
) -> EvaluationScore:
    """Submit an evaluation score for a specific criterion."""
    if evaluation.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation has already been finalized",
        )

    # Check for duplicate
    existing = await EvaluationScore.objects.filter_by(
        evaluation_id=evaluation.id,
        evaluator_id=evaluator_id,
        criterion_name=payload.criterion_name,
    ).all(session)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Already scored criterion '{payload.criterion_name}'",
        )

    now = utcnow()
    score = EvaluationScore(
        evaluation_id=evaluation.id,
        evaluator_id=evaluator_id,
        criterion_name=payload.criterion_name,
        criterion_weight=payload.criterion_weight,
        score=payload.score,
        rationale=payload.rationale,
        created_at=now,
    )
    session.add(score)

    # Transition to in_review if first score
    if evaluation.status == "pending":
        evaluation.status = "in_review"
        evaluation.updated_at = now
        session.add(evaluation)

    await session.commit()
    await session.refresh(score)
    return score


async def finalize_evaluation(
    session: AsyncSession,
    *,
    evaluation: Evaluation,
    finalized_by: UUID,
) -> Evaluation:
    """Finalize an evaluation: aggregate scores and generate incentive signals."""
    if evaluation.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Evaluation has already been finalized",
        )

    scores = await EvaluationScore.objects.filter_by(
        evaluation_id=evaluation.id,
    ).all(session)

    if not scores:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot finalize evaluation with no scores",
        )

    # Aggregate scores: weighted average
    aggregate = _aggregate_scores(scores)

    now = utcnow()
    evaluation.status = "completed"
    evaluation.aggregate_result = aggregate
    evaluation.updated_at = now
    session.add(evaluation)

    # Generate incentive signals for executor
    signals = _generate_incentive_signals(
        evaluation=evaluation,
        aggregate=aggregate,
    )
    for signal in signals:
        session.add(signal)

    # Generate reviewer incentive signals (reputation feedback loop)
    reviewer_signals = await generate_reviewer_incentive_signals(
        session, evaluation=evaluation,
    )
    for signal in reviewer_signals:
        session.add(signal)

    await record_audit(
        session,
        organization_id=evaluation.organization_id,
        actor_id=finalized_by,
        actor_type="human",
        action="evaluation.finalize",
        zone_id=evaluation.zone_id,
        target_type="evaluation",
        target_id=evaluation.id,
        payload=aggregate,
        commit=False,
    )

    await session.commit()
    await session.refresh(evaluation)
    return evaluation


def _aggregate_scores(scores: list[EvaluationScore]) -> dict[str, object]:
    """Compute weighted average and per-criterion aggregates."""
    total_weight = 0.0
    weighted_sum = 0.0
    criteria: dict[str, dict[str, object]] = {}

    for score in scores:
        total_weight += score.criterion_weight
        weighted_sum += score.score * score.criterion_weight

        if score.criterion_name not in criteria:
            criteria[score.criterion_name] = {
                "scores": [],
                "weight": score.criterion_weight,
            }
        scores_list = criteria[score.criterion_name]["scores"]
        if isinstance(scores_list, list):
            scores_list.append(score.score)

    overall = weighted_sum / total_weight if total_weight > 0 else 0.0

    # Compute per-criterion averages
    criterion_averages: dict[str, float] = {}
    for name, data in criteria.items():
        scores_list = data["scores"]
        if isinstance(scores_list, list) and scores_list:
            criterion_averages[name] = sum(scores_list) / len(scores_list)

    return {
        "overall_score": round(overall, 3),
        "total_scores": len(scores),
        "criterion_averages": criterion_averages,
    }


def _generate_incentive_signals(
    *,
    evaluation: Evaluation,
    aggregate: dict[str, object],
) -> list[IncentiveSignal]:
    """Generate incentive signals based on evaluation aggregate."""
    overall = aggregate.get("overall_score", 0.0)
    if not isinstance(overall, (int, float)):
        return []

    now = utcnow()

    if overall >= 0.8:
        signal_type = "positive"
        magnitude = min(overall * 1.5, 2.0)
        reason = f"High evaluation score: {overall:.2f}"
    elif overall >= 0.4:
        signal_type = "neutral"
        magnitude = 0.5
        reason = f"Average evaluation score: {overall:.2f}"
    else:
        signal_type = "negative"
        magnitude = max(1.0 - overall, 0.5)
        reason = f"Low evaluation score: {overall:.2f}"

    return [
        IncentiveSignal(
            evaluation_id=evaluation.id,
            target_id=evaluation.executor_id,
            signal_type=signal_type,
            magnitude=round(magnitude, 3),
            reason=reason,
            applied=False,
            created_at=now,
        )
    ]


async def generate_reviewer_incentive_signals(
    session: AsyncSession,
    *,
    evaluation: Evaluation,
) -> list[IncentiveSignal]:
    """Generate positive incentive signals for reviewers who performed well.

    Rewards reviewers whose GardenerFeedback shows reviewed_in_time=True
    and decision_overturned=False for the proposal associated with this evaluation.
    """
    if evaluation.proposal_id is None:
        return []

    from app.models.gardener_feedback import GardenerFeedback

    feedback_entries = await GardenerFeedback.objects.filter_by(
        proposal_id=evaluation.proposal_id,
    ).all(session)

    now = utcnow()
    signals: list[IncentiveSignal] = []
    for entry in feedback_entries:
        if entry.reviewed_in_time is True and entry.decision_overturned is False:
            signal = IncentiveSignal(
                evaluation_id=evaluation.id,
                target_id=entry.reviewer_id,
                signal_type="positive",
                magnitude=0.3,
                reason="Good reviewer: timely review with non-overturned decision",
                applied=False,
                created_at=now,
            )
            signals.append(signal)

    return signals


async def apply_incentive_signals(
    session: AsyncSession,
    *,
    evaluation: Evaluation,
) -> int:
    """Apply unapplied incentive signals to update member reputation scores.

    Returns the number of signals applied.
    """
    signals = await IncentiveSignal.objects.filter_by(
        evaluation_id=evaluation.id,
        applied=False,
    ).all(session)

    applied_count = 0
    for signal in signals:
        member = await OrganizationMember.objects.by_id(signal.target_id).first(session)
        if member is None:
            continue

        delta = signal.magnitude if signal.signal_type == "positive" else -signal.magnitude
        if signal.signal_type == "neutral":
            delta = 0.0

        member.reputation_score = max(0.0, member.reputation_score + delta)
        session.add(member)

        signal.applied = True
        session.add(signal)
        applied_count += 1

    if applied_count > 0:
        await session.commit()

    return applied_count


# ---------------------------------------------------------------------------
# Automated / LLM evaluation
# ---------------------------------------------------------------------------


def _run_automated_check(
    criterion: dict[str, object],
    evaluation: Evaluation,
    zone: TrustZone,
) -> tuple[float, str]:
    """Run an automated rule-based check and return (score, rationale)."""
    config = criterion.get("config", {})
    if not isinstance(config, dict):
        config = {}

    name = criterion.get("name", "unknown")

    # Timeliness check: was evaluation created within max_days of the proposal/task?
    max_days = config.get("max_days")
    if max_days is not None and isinstance(max_days, (int, float)):
        if evaluation.created_at is not None:
            now = utcnow()
            elapsed_days = (now - evaluation.created_at).total_seconds() / 86400
            if elapsed_days <= max_days:
                return 1.0, f"Within {max_days}-day window (elapsed: {elapsed_days:.1f} days)"
            else:
                # Scale down linearly: 0 at 2x the window
                score = max(0.0, 1.0 - (elapsed_days - max_days) / max_days)
                return round(score, 3), f"Exceeded {max_days}-day window (elapsed: {elapsed_days:.1f} days)"

    return 0.5, f"No automated check configuration matched for criterion '{name}'"


async def _run_llm_review(
    criterion: dict[str, object],
    evaluation: Evaluation,
    zone: TrustZone,
) -> tuple[float, str]:
    """Run an LLM-powered review and return (score, rationale)."""
    config = criterion.get("config", {})
    if not isinstance(config, dict):
        config = {}

    prompt = config.get("prompt", "Evaluate the quality of the completed work.")

    try:
        import anthropic

        from app.core.config import settings

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        context = (
            f"Evaluation ID: {evaluation.id}\n"
            f"Zone: {zone.name}\n"
            f"Executor: {evaluation.executor_id}\n"
            f"Proposal ID: {evaluation.proposal_id or 'N/A'}\n"
            f"Task ID: {evaluation.task_id or 'N/A'}\n"
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{prompt}\n\n"
                        f"Context:\n{context}\n\n"
                        "Respond with a JSON object: {\"score\": <0.0-1.0>, \"rationale\": \"<explanation>\"}"
                    ),
                }
            ],
        )

        import json

        response_text = message.content[0].text
        start = response_text.index("{")
        end = response_text.rindex("}") + 1
        result = json.loads(response_text[start:end])

        score = float(result.get("score", 0.5))
        score = max(0.0, min(1.0, score))
        rationale = str(result.get("rationale", "LLM review completed"))
        return round(score, 3), rationale

    except Exception as exc:
        logger.warning("LLM review failed: %s", exc, exc_info=True)
        return 0.5, "LLM review failed"


async def auto_evaluate(
    session: AsyncSession,
    evaluation: Evaluation,
    zone: TrustZone,
) -> list[EvaluationScore]:
    """Run automated evaluation criteria and submit scores as system evaluator.

    Reads zone.evaluation_criteria for criteria definitions:
    {
        "criteria": [
            {"name": "timeliness", "type": "automated_check", "weight": 1.0, "config": {"max_days": 7}},
            {"name": "quality_review", "type": "llm_review", "weight": 2.0, "config": {"prompt": "..."}}
        ]
    }
    """
    from app.schemas.evaluations import EvaluationScoreCreate

    criteria_config = zone.evaluation_criteria
    if not criteria_config or not isinstance(criteria_config, dict):
        return []

    criteria_list = criteria_config.get("criteria", [])
    if not isinstance(criteria_list, list):
        return []

    created_scores: list[EvaluationScore] = []

    for criterion in criteria_list:
        if not isinstance(criterion, dict):
            continue

        criterion_type = criterion.get("type")
        name = str(criterion.get("name", "unnamed"))
        weight = float(criterion.get("weight", 1.0))

        if criterion_type == "automated_check":
            score_val, rationale = _run_automated_check(criterion, evaluation, zone)
        elif criterion_type == "llm_review":
            score_val, rationale = await _run_llm_review(criterion, evaluation, zone)
        else:
            logger.warning("Unknown criterion type '%s' for criterion '%s'", criterion_type, name)
            continue

        score_payload = EvaluationScoreCreate(
            criterion_name=name,
            criterion_weight=weight,
            score=score_val,
            rationale=rationale,
        )

        try:
            score = await submit_score(
                session,
                evaluation=evaluation,
                evaluator_id=SYSTEM_EVALUATOR_ID,
                payload=score_payload,
            )
            created_scores.append(score)
        except HTTPException:
            logger.warning(
                "Failed to submit auto-eval score for criterion '%s'",
                name,
                exc_info=True,
            )

    return created_scores
