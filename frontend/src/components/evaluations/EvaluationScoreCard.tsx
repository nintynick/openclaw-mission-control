"use client";

import { cn } from "@/lib/utils";

type ScoreEntry = {
  id: string;
  criterion_name: string;
  criterion_weight: number;
  score: number;
  rationale: string;
  evaluator_id: string;
};

type EvaluationScoreCardProps = {
  scores: ScoreEntry[];
  aggregateResult?: {
    overall_score?: number;
    criterion_averages?: Record<string, number>;
  } | null;
};

export function EvaluationScoreCard({
  scores,
  aggregateResult,
}: EvaluationScoreCardProps) {
  if (scores.length === 0 && !aggregateResult) {
    return (
      <p className="text-sm text-slate-500">No scores submitted yet.</p>
    );
  }

  const overallScore = aggregateResult?.overall_score;
  const criterionAverages = aggregateResult?.criterion_averages ?? {};

  return (
    <div className="space-y-4">
      {overallScore != null ? (
        <div className="rounded-lg bg-slate-50 p-4 text-center">
          <p className="text-xs font-medium text-slate-500">Overall Score</p>
          <p
            className={cn(
              "text-3xl font-bold",
              overallScore >= 0.8 && "text-emerald-600",
              overallScore >= 0.4 && overallScore < 0.8 && "text-amber-600",
              overallScore < 0.4 && "text-rose-600",
            )}
          >
            {(overallScore * 100).toFixed(0)}%
          </p>
        </div>
      ) : null}

      {Object.keys(criterionAverages).length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-slate-600">
            Criterion Averages
          </p>
          {Object.entries(criterionAverages).map(([name, avg]) => (
            <div key={name} className="flex items-center justify-between">
              <span className="text-sm capitalize text-slate-700">{name}</span>
              <div className="flex items-center gap-2">
                <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      avg >= 0.8 && "bg-emerald-500",
                      avg >= 0.4 && avg < 0.8 && "bg-amber-500",
                      avg < 0.4 && "bg-rose-500",
                    )}
                    style={{ width: `${avg * 100}%` }}
                  />
                </div>
                <span className="text-xs font-medium text-slate-600">
                  {(avg * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {scores.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-medium text-slate-600">
            Individual Scores
          </p>
          {scores.map((score) => (
            <div
              key={score.id}
              className="rounded-lg border border-slate-100 p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium capitalize text-slate-700">
                  {score.criterion_name}
                </span>
                <span className="text-sm font-semibold text-slate-800">
                  {(score.score * 100).toFixed(0)}%
                </span>
              </div>
              <p className="mt-0.5 text-xs text-slate-500">
                by {String(score.evaluator_id).slice(0, 8)}...
                {score.criterion_weight !== 1.0
                  ? ` (weight: ${score.criterion_weight})`
                  : ""}
              </p>
              {score.rationale ? (
                <p className="mt-1 text-xs text-slate-600">
                  {score.rationale}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
