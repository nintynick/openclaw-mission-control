# ruff: noqa

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

import pytest

from app.models.evaluations import Evaluation, EvaluationScore, IncentiveSignal
from app.services.evaluations import _aggregate_scores, _generate_incentive_signals


def test_evaluation_model_defaults() -> None:
    ev = Evaluation(
        zone_id=uuid4(),
        organization_id=uuid4(),
        executor_id=uuid4(),
    )
    assert ev.status == "pending"
    assert ev.aggregate_result is None
    assert ev.task_id is None
    assert ev.proposal_id is None
    assert ev.created_at is not None
    assert ev.updated_at is not None


def test_evaluation_score_model_defaults() -> None:
    score = EvaluationScore(
        evaluation_id=uuid4(),
        evaluator_id=uuid4(),
        criterion_name="quality",
        score=0.85,
    )
    assert score.criterion_weight == 1.0
    assert score.rationale == ""
    assert score.created_at is not None


def test_incentive_signal_model_defaults() -> None:
    signal = IncentiveSignal(
        evaluation_id=uuid4(),
        target_id=uuid4(),
        signal_type="positive",
    )
    assert signal.magnitude == 1.0
    assert signal.reason == ""
    assert signal.applied is False
    assert signal.created_at is not None


def test_aggregate_scores_single_criterion() -> None:
    scores = [
        EvaluationScore(
            evaluation_id=uuid4(),
            evaluator_id=uuid4(),
            criterion_name="quality",
            criterion_weight=1.0,
            score=0.9,
        ),
    ]
    result = _aggregate_scores(scores)
    assert result["overall_score"] == 0.9
    assert result["total_scores"] == 1
    assert result["criterion_averages"]["quality"] == 0.9


def test_aggregate_scores_multiple_criteria() -> None:
    eval_id = uuid4()
    scores = [
        EvaluationScore(
            evaluation_id=eval_id,
            evaluator_id=uuid4(),
            criterion_name="quality",
            criterion_weight=2.0,
            score=0.8,
        ),
        EvaluationScore(
            evaluation_id=eval_id,
            evaluator_id=uuid4(),
            criterion_name="timeliness",
            criterion_weight=1.0,
            score=1.0,
        ),
    ]
    result = _aggregate_scores(scores)
    # Weighted average: (0.8 * 2.0 + 1.0 * 1.0) / (2.0 + 1.0) = 2.6 / 3.0 = 0.867
    assert abs(result["overall_score"] - 0.867) < 0.01
    assert result["total_scores"] == 2


def test_aggregate_scores_multiple_evaluators_same_criterion() -> None:
    eval_id = uuid4()
    scores = [
        EvaluationScore(
            evaluation_id=eval_id,
            evaluator_id=uuid4(),
            criterion_name="quality",
            criterion_weight=1.0,
            score=0.6,
        ),
        EvaluationScore(
            evaluation_id=eval_id,
            evaluator_id=uuid4(),
            criterion_name="quality",
            criterion_weight=1.0,
            score=0.8,
        ),
    ]
    result = _aggregate_scores(scores)
    assert result["criterion_averages"]["quality"] == 0.7


def test_aggregate_scores_empty() -> None:
    result = _aggregate_scores([])
    assert result["overall_score"] == 0.0
    assert result["total_scores"] == 0


def test_generate_incentive_signals_high_score() -> None:
    eval = Evaluation(
        id=uuid4(),
        zone_id=uuid4(),
        organization_id=uuid4(),
        executor_id=uuid4(),
    )
    signals = _generate_incentive_signals(
        evaluation=eval,
        aggregate={"overall_score": 0.9},
    )
    assert len(signals) == 1
    assert signals[0].signal_type == "positive"
    assert signals[0].target_id == eval.executor_id


def test_generate_incentive_signals_medium_score() -> None:
    eval = Evaluation(
        id=uuid4(),
        zone_id=uuid4(),
        organization_id=uuid4(),
        executor_id=uuid4(),
    )
    signals = _generate_incentive_signals(
        evaluation=eval,
        aggregate={"overall_score": 0.5},
    )
    assert len(signals) == 1
    assert signals[0].signal_type == "neutral"


def test_generate_incentive_signals_low_score() -> None:
    eval = Evaluation(
        id=uuid4(),
        zone_id=uuid4(),
        organization_id=uuid4(),
        executor_id=uuid4(),
    )
    signals = _generate_incentive_signals(
        evaluation=eval,
        aggregate={"overall_score": 0.2},
    )
    assert len(signals) == 1
    assert signals[0].signal_type == "negative"


def test_generate_incentive_signals_boundary_08() -> None:
    eval = Evaluation(
        id=uuid4(),
        zone_id=uuid4(),
        organization_id=uuid4(),
        executor_id=uuid4(),
    )
    signals = _generate_incentive_signals(
        evaluation=eval,
        aggregate={"overall_score": 0.8},
    )
    assert signals[0].signal_type == "positive"


def test_generate_incentive_signals_boundary_04() -> None:
    eval = Evaluation(
        id=uuid4(),
        zone_id=uuid4(),
        organization_id=uuid4(),
        executor_id=uuid4(),
    )
    signals = _generate_incentive_signals(
        evaluation=eval,
        aggregate={"overall_score": 0.4},
    )
    assert signals[0].signal_type == "neutral"
