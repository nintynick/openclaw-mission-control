"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";

import { useAuth } from "@/auth/clerk";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { EscalationsTable } from "@/components/escalations/EscalationsTable";
import {
  type listEscalationsApiV1OrganizationsMeEscalationsGetResponse,
  useListEscalationsApiV1OrganizationsMeEscalationsGet,
} from "@/api/generated/escalations/escalations";
import { ApiError } from "@/api/mutator";

export default function EscalationsPage() {
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const [activeTab, setActiveTab] = useState<"action" | "governance" | "all">(
    "all",
  );

  const escalationsQuery =
    useListEscalationsApiV1OrganizationsMeEscalationsGet<
      listEscalationsApiV1OrganizationsMeEscalationsGetResponse,
      ApiError
    >(
      activeTab !== "all" ? { escalation_type: activeTab } : undefined,
      {
        query: {
          enabled: Boolean(isSignedIn),
          refetchInterval: 15_000,
          refetchOnMount: "always",
        },
      },
    );

  const escalations = useMemo(
    () =>
      escalationsQuery.data?.status === 200
        ? (escalationsQuery.data.data ?? [])
        : [],
    [escalationsQuery.data],
  );

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view escalations.",
        forceRedirectUrl: "/escalations",
      }}
      title="Escalations"
      description="Review and manage action and governance escalations"
      headerActions={
        <div className="flex items-center rounded-lg border border-slate-200 bg-white">
          <button
            type="button"
            onClick={() => setActiveTab("all")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              activeTab === "all"
                ? "bg-slate-100 text-slate-800"
                : "text-slate-500 hover:text-slate-700"
            } rounded-l-lg`}
          >
            All
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("action")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              activeTab === "action"
                ? "bg-slate-100 text-slate-800"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Action
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("governance")}
            className={`px-3 py-1.5 text-xs font-medium transition ${
              activeTab === "governance"
                ? "bg-slate-100 text-slate-800"
                : "text-slate-500 hover:text-slate-700"
            } rounded-r-lg`}
          >
            Governance
          </button>
        </div>
      }
      stickyHeader
    >
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <EscalationsTable
          escalations={escalations as any[]}
          isLoading={escalationsQuery.isLoading}
          stickyHeader
          emptyState={{
            title:
              activeTab === "all"
                ? "No escalations yet"
                : `No ${activeTab} escalations`,
            description:
              activeTab === "all"
                ? "Escalations will appear here when triggered from proposals or zones."
                : `No ${activeTab} escalations at this time.`,
          }}
        />
      </div>
    </DashboardPageLayout>
  );
}
