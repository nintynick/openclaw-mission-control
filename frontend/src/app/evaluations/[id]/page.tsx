"use client";

export const dynamic = "force-dynamic";

import { useMemo } from "react";
import { useParams } from "next/navigation";

import { useAuth } from "@/auth/clerk";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { StatusPill } from "@/components/atoms/StatusPill";
import { EvaluationScoreCard } from "@/components/evaluations/EvaluationScoreCard";
import { useGetEvaluationApiV1OrganizationsMeEvaluationsEvaluationIdGet } from "@/api/generated/evaluations/evaluations";
import { ApiError } from "@/api/mutator";

function truncateId(id: string) {
  return id.length > 8 ? `${id.slice(0, 8)}...` : id;
}

function formatTimestamp(ts: string) {
  return new Date(ts).toLocaleString();
}

export default function EvaluationDetailPage() {
  const params = useParams();
  const evaluationId = Array.isArray(params?.id) ? params.id[0] : params?.id;
  const { isSignedIn } = useAuth();

  const evalQuery =
    useGetEvaluationApiV1OrganizationsMeEvaluationsEvaluationIdGet<
      any,
      ApiError
    >(evaluationId!, {
      query: { enabled: Boolean(isSignedIn && evaluationId) },
    });

  const evaluation =
    evalQuery.data?.status === 200 ? evalQuery.data.data : null;

  const scores = useMemo(
    () => evaluation?.scores ?? [],
    [evaluation?.scores],
  );

  const signals = useMemo(
    () => evaluation?.incentive_signals ?? [],
    [evaluation?.incentive_signals],
  );

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view evaluation details.",
        forceRedirectUrl: `/evaluations/${evaluationId}`,
      }}
      title={
        evaluation ? (
          <span className="flex items-center gap-3">
            Evaluation {truncateId(evaluation.id)}
            <StatusPill status={evaluation.status} />
          </span>
        ) : (
          "Evaluation Detail"
        )
      }
    >
      {evaluation ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Left column: Metadata + Scores */}
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">Metadata</h3>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Zone ID</dt>
                  <dd className="font-mono text-slate-700">
                    {truncateId(evaluation.zone_id)}
                  </dd>
                </div>
                {evaluation.proposal_id ? (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Proposal ID</dt>
                    <dd className="font-mono text-slate-700">
                      {truncateId(evaluation.proposal_id)}
                    </dd>
                  </div>
                ) : null}
                <div className="flex justify-between">
                  <dt className="text-slate-500">Executor ID</dt>
                  <dd className="font-mono text-slate-700">
                    {truncateId(evaluation.executor_id)}
                  </dd>
                </div>
                {evaluation.task_id ? (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Task ID</dt>
                    <dd className="font-mono text-slate-700">
                      {truncateId(evaluation.task_id)}
                    </dd>
                  </div>
                ) : null}
                <div className="flex justify-between">
                  <dt className="text-slate-500">Created</dt>
                  <dd className="text-slate-700">
                    {formatTimestamp(evaluation.created_at)}
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Updated</dt>
                  <dd className="text-slate-700">
                    {formatTimestamp(evaluation.updated_at)}
                  </dd>
                </div>
              </dl>
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-sm font-semibold text-slate-800">
                Scores
              </h3>
              <EvaluationScoreCard
                scores={scores}
                aggregateResult={evaluation.aggregate_result}
              />
            </div>
          </div>

          {/* Right column: Incentive Signals */}
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">
                Incentive Signals ({signals.length})
              </h3>
              {signals.length > 0 ? (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                        <th className="pb-2 pr-4">Target ID</th>
                        <th className="pb-2 pr-4">Type</th>
                        <th className="pb-2 pr-4">Magnitude</th>
                        <th className="pb-2 pr-4">Reason</th>
                        <th className="pb-2">Applied</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {signals.map((signal: any) => (
                        <tr key={signal.id}>
                          <td className="py-2 pr-4 font-mono text-slate-700">
                            {truncateId(signal.target_id)}
                          </td>
                          <td className="py-2 pr-4">
                            <StatusPill status={signal.signal_type} />
                          </td>
                          <td className="py-2 pr-4 text-slate-700">
                            {signal.magnitude}
                          </td>
                          <td className="py-2 pr-4 text-slate-600">
                            {signal.reason}
                          </td>
                          <td className="py-2">
                            <span
                              className={
                                signal.applied
                                  ? "text-emerald-600"
                                  : "text-slate-400"
                              }
                            >
                              {signal.applied ? "Yes" : "No"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-500">
                  No incentive signals generated yet.
                </p>
              )}
            </div>
          </div>
        </div>
      ) : evalQuery.isLoading ? (
        <p className="text-sm text-slate-500">Loading...</p>
      ) : (
        <p className="text-sm text-red-500">Evaluation not found.</p>
      )}
    </DashboardPageLayout>
  );
}
