"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";

import { useAuth } from "@/auth/clerk";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { ProposalsTable } from "@/components/proposals/ProposalsTable";
import {
  type listProposalsApiV1OrganizationsMeProposalsGetResponse,
  useListProposalsApiV1OrganizationsMeProposalsGet,
} from "@/api/generated/proposals/proposals";
import { ApiError } from "@/api/mutator";

export default function ProposalsPage() {
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const [activeTab, setActiveTab] = useState<"pending" | "all">("pending");

  const proposalsQuery = useListProposalsApiV1OrganizationsMeProposalsGet<
    listProposalsApiV1OrganizationsMeProposalsGetResponse,
    ApiError
  >(
    activeTab === "pending" ? { proposal_status: "pending_review" } : undefined,
    {
      query: {
        enabled: Boolean(isSignedIn),
        refetchInterval: 15_000,
        refetchOnMount: "always",
      },
    },
  );

  const proposals = useMemo(
    () =>
      proposalsQuery.data?.status === 200
        ? (proposalsQuery.data.data ?? [])
        : [],
    [proposalsQuery.data],
  );

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view proposals.",
        forceRedirectUrl: "/proposals",
      }}
      title="Proposals"
      description="Review and vote on governance proposals"
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
        <ProposalsTable
          proposals={proposals as any[]}
          isLoading={proposalsQuery.isLoading}
          stickyHeader
          emptyState={{
            title:
              activeTab === "pending"
                ? "No pending proposals"
                : "No proposals yet",
            description:
              activeTab === "pending"
                ? "All proposals have been reviewed."
                : "Proposals will appear here when created from trust zones.",
          }}
        />
      </div>
    </DashboardPageLayout>
  );
}
