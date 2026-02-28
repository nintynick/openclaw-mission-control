"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";

import { useAuth } from "@/auth/clerk";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { EvaluationsTable } from "@/components/evaluations/EvaluationsTable";
import {
  type listEvaluationsApiV1OrganizationsMeEvaluationsGetResponse,
  useListEvaluationsApiV1OrganizationsMeEvaluationsGet,
} from "@/api/generated/evaluations/evaluations";
import { ApiError } from "@/api/mutator";

export default function EvaluationsPage() {
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const [activeTab, setActiveTab] = useState<"pending" | "completed" | "all">(
    "pending",
  );

  const evaluationsQuery =
    useListEvaluationsApiV1OrganizationsMeEvaluationsGet<
      listEvaluationsApiV1OrganizationsMeEvaluationsGetResponse,
      ApiError
    >(
      activeTab !== "all"
        ? { evaluation_status: activeTab === "pending" ? "pending" : "completed" }
        : undefined,
      {
        query: {
          enabled: Boolean(isSignedIn),
          refetchInterval: 15_000,
          refetchOnMount: "always",
        },
      },
    );

  const evaluations = useMemo(
    () =>
      evaluationsQuery.data?.status === 200
        ? (evaluationsQuery.data.data ?? [])
        : [],
    [evaluationsQuery.data],
  );

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view evaluations.",
        forceRedirectUrl: "/evaluations",
      }}
      title="Evaluations"
      description="Review post-completion evaluations and scores"
      headerActions={
        <div className="flex items-center rounded-lg border border-slate-200 bg-white">
          <button
            type="button"
            onClick={() => setActiveTab("pending")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              activeTab === "pending"
                ? "bg-slate-100 text-slate-800"
                : "text-slate-500 hover:text-slate-700"
            } rounded-l-lg`}
          >
            Pending
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("completed")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              activeTab === "completed"
                ? "bg-slate-100 text-slate-800"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Completed
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              activeTab === "all"
                ? "bg-slate-100 text-slate-800"
                : "text-slate-500 hover:text-slate-700"
            } rounded-r-lg`}
          >
            All
          </button>
        </div>
      }
      stickyHeader
    >
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <EvaluationsTable
          evaluations={evaluations as any[]}
          isLoading={evaluationsQuery.isLoading}
          stickyHeader
          emptyState={{
            title:
              activeTab === "pending"
                ? "No pending evaluations"
                : activeTab === "completed"
                  ? "No completed evaluations"
                  : "No evaluations yet",
            description:
              activeTab === "pending"
                ? "Evaluations will appear here when tasks are completed."
                : activeTab === "completed"
                  ? "No evaluations have been finalized."
                  : "Evaluations will appear here when tasks are completed.",
          }}
        />
      </div>
    </DashboardPageLayout>
  );
}
