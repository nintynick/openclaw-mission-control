"""Gardener intelligence service for LLM-powered reviewer selection.

Uses the Anthropic Claude API to intelligently select reviewers for proposals
based on zone context, candidate profiles, and historical outcomes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.core.time import utcnow
from app.models.gardener_feedback import GardenerFeedback
from app.models.organization_members import OrganizationMember
from app.models.trust_zones import TrustZone
from app.models.zone_assignments import ZoneAssignment

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.proposals import Proposal

logger = get_logger(__name__)

GARDENER_SYSTEM_PROMPT = """You are a Gardener — an AI governance facilitator responsible for selecting the best reviewers for proposals within a trust zone hierarchy.

Your role embodies the delegation trilemma: balancing capability, alignment, and availability when choosing who should review a proposal.

## Selection Principles

1. **Capability Match**: Select reviewers whose expertise aligns with the proposal type and zone responsibilities.
2. **Alignment Check**: Prefer reviewers with established track records in the zone or related zones.
3. **Availability**: Consider reviewer workload and response history.
4. **Risk Scaling**: Higher-impact proposals warrant more experienced reviewers.
5. **Diversity**: When possible, select reviewers with complementary perspectives.
6. **Review Quality**: When available, consider review_accuracy (fraction of reviews where the reviewer's decision was not overturned) and response_rate (fraction of reviews completed on time). Prefer reviewers with higher accuracy and response rates.

## Output Format

Respond with a JSON object:
```json
{
  "selections": [
    {
      "reviewer_id": "<uuid>",
      "reason": "<brief explanation of why this reviewer was selected>"
    }
  ],
  "reasoning": "<overall reasoning for the selection strategy>"
}
```

Select between 1 and 5 reviewers based on the proposal complexity and zone decision model."""

DEFAULT_MODEL = "claude-sonnet-4-20250514"


@dataclass
class ReviewerCandidate:
    """A candidate reviewer with their profile and history."""

    member_id: UUID
    role: str
    zone_assignments: list[str] = field(default_factory=list)
    reputation_score: float = 0.0
    past_review_count: int = 0
    avg_response_time_hours: float | None = None
    review_accuracy: float | None = None
    response_rate: float | None = None


@dataclass
class ReviewerSelection:
    """A selected reviewer with reasoning."""

    reviewer_id: UUID
    reason: str


class GardenerService:
    """LLM-powered reviewer selection service."""

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL) -> None:
        if api_key is None:
            from app.core.config import settings

            if settings.anthropic_api_key:
                api_key = settings.anthropic_api_key
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        """Lazily initialize the Anthropic client."""
        if self._client is None:
            import anthropic

            if self._api_key:
                self._client = anthropic.Anthropic(api_key=self._api_key)
            else:
                # Will use ANTHROPIC_API_KEY env var
                self._client = anthropic.Anthropic()
        return self._client

    async def select_reviewers(
        self,
        session: AsyncSession,
        *,
        proposal: Proposal,
        zone: TrustZone,
        candidates: list[ReviewerCandidate],
        max_reviewers: int = 3,
    ) -> list[ReviewerSelection]:
        """Select reviewers using the Gardener AI.

        Falls back to rule-based selection if the API call fails.
        """
        if not candidates:
            return []

        try:
            context = self._build_context(
                proposal=proposal,
                zone=zone,
                candidates=candidates,
                max_reviewers=max_reviewers,
            )
            selections = await self._call_llm(context)
            selection_method = "gardener_ai"
        except Exception:
            logger.warning(
                "Gardener AI selection failed, falling back to rule-based",
                exc_info=True,
            )
            selections = self._rule_based_fallback(candidates, max_reviewers)
            selection_method = "rule_based"

        # Record feedback entries
        now = utcnow()
        for selection in selections:
            feedback = GardenerFeedback(
                proposal_id=proposal.id,
                reviewer_id=selection.reviewer_id,
                selected_by=selection_method,
                created_at=now,
                updated_at=now,
            )
            session.add(feedback)

        return selections

    def _build_context(
        self,
        *,
        proposal: Proposal,
        zone: TrustZone,
        candidates: list[ReviewerCandidate],
        max_reviewers: int,
    ) -> str:
        """Build the context message for the Gardener LLM."""
        candidate_descriptions = []
        for c in candidates:
            desc = {
                "member_id": str(c.member_id),
                "role": c.role,
                "zone_assignments": c.zone_assignments,
                "reputation_score": c.reputation_score,
                "past_review_count": c.past_review_count,
            }
            if c.avg_response_time_hours is not None:
                desc["avg_response_time_hours"] = c.avg_response_time_hours
            if c.review_accuracy is not None:
                desc["review_accuracy"] = round(c.review_accuracy, 3)
            if c.response_rate is not None:
                desc["response_rate"] = round(c.response_rate, 3)
            candidate_descriptions.append(desc)

        context = {
            "proposal": {
                "id": str(proposal.id),
                "title": proposal.title,
                "description": proposal.description,
                "type": proposal.proposal_type,
                "zone_id": str(proposal.zone_id),
            },
            "zone": {
                "id": str(zone.id),
                "name": zone.name,
                "responsibilities": zone.responsibilities,
                "agent_qualifications": zone.agent_qualifications,
                "decision_model": zone.decision_model,
            },
            "candidates": candidate_descriptions,
            "max_reviewers": max_reviewers,
        }

        return json.dumps(context, indent=2, default=str)

    async def _call_llm(self, context: str) -> list[ReviewerSelection]:
        """Call the Anthropic Claude API for reviewer selection."""
        client = self._get_client()

        message = client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=GARDENER_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Select the best reviewers for this proposal:\n\n{context}",
                }
            ],
        )

        # Parse the response
        response_text = message.content[0].text
        # Extract JSON from the response
        try:
            # Try to find JSON in the response
            start = response_text.index("{")
            end = response_text.rindex("}") + 1
            result = json.loads(response_text[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.warning("Failed to parse Gardener response as JSON")
            raise

        from uuid import UUID as _UUID

        selections = []
        for s in result.get("selections", []):
            try:
                selections.append(
                    ReviewerSelection(
                        reviewer_id=_UUID(s["reviewer_id"]),
                        reason=s.get("reason", "Selected by Gardener AI"),
                    )
                )
            except (KeyError, ValueError):
                continue

        return selections

    @staticmethod
    def _rule_based_fallback(
        candidates: list[ReviewerCandidate],
        max_reviewers: int,
    ) -> list[ReviewerSelection]:
        """Simple rule-based fallback when LLM is unavailable."""
        # Sort by: approver role first, then review accuracy, response rate,
        # reputation score, and past review count (all descending)
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (
                0 if c.role == "approver" else 1,
                -(c.review_accuracy if c.review_accuracy is not None else 0.0),
                -(c.response_rate if c.response_rate is not None else 0.0),
                -c.reputation_score,
                -c.past_review_count,
            ),
        )

        selections = []
        for c in sorted_candidates[:max_reviewers]:
            selections.append(
                ReviewerSelection(
                    reviewer_id=c.member_id,
                    reason=f"Rule-based selection: {c.role} with reputation {c.reputation_score:.1f}",
                )
            )

        return selections


async def build_candidates(
    session: AsyncSession,
    *,
    zone: TrustZone,
    exclude_user_id: UUID | None = None,
) -> list[ReviewerCandidate]:
    """Build a list of reviewer candidates from zone assignments and org members."""
    assignments = await ZoneAssignment.objects.filter_by(
        zone_id=zone.id,
    ).all(session)

    candidates: list[ReviewerCandidate] = []
    seen_members: set[UUID] = set()

    for assignment in assignments:
        if assignment.role not in ("approver", "gardener", "evaluator"):
            continue
        if assignment.member_id in seen_members:
            continue
        if exclude_user_id and assignment.member_id == exclude_user_id:
            continue

        seen_members.add(assignment.member_id)

        member = await OrganizationMember.objects.by_id(
            assignment.member_id
        ).first(session)

        reputation = member.reputation_score if member else 0.0

        # Count past feedback entries for this reviewer
        past_feedback = await GardenerFeedback.objects.filter_by(
            reviewer_id=assignment.member_id,
        ).all(session)

        # Compute review_accuracy and response_rate from feedback
        review_accuracy: float | None = None
        response_rate: float | None = None
        completed = [f for f in past_feedback if f.work_outcome is not None]
        if completed:
            review_accuracy = sum(
                1 for f in completed if f.decision_overturned is False
            ) / len(completed)
            response_rate = sum(
                1 for f in completed if f.reviewed_in_time is True
            ) / len(completed)

        candidates.append(
            ReviewerCandidate(
                member_id=assignment.member_id,
                role=assignment.role,
                zone_assignments=[assignment.role],
                reputation_score=reputation,
                past_review_count=len(past_feedback),
                review_accuracy=review_accuracy,
                response_rate=response_rate,
            )
        )

    return candidates
