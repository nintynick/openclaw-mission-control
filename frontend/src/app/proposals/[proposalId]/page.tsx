"use client";

export const dynamic = "force-dynamic";

import { useMemo } from "react";
import { useParams } from "next/navigation";

import { useAuth } from "@/auth/clerk";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { StatusPill } from "@/components/atoms/StatusPill";
import { ApprovalStatusTracker } from "@/components/proposals/ApprovalStatusTracker";
import { VoteButton } from "@/components/proposals/VoteButton";
import { EscalationDialog } from "@/components/escalations/EscalationDialog";
import {
  useGetProposalApiV1OrganizationsMeProposalsProposalIdGet,
  useApproveProposalApiV1OrganizationsMeProposalsProposalIdApprovePost,
  useRejectProposalApiV1OrganizationsMeProposalsProposalIdRejectPost,
  useAbstainProposalApiV1OrganizationsMeProposalsProposalIdAbstainPost,
} from "@/api/generated/proposals/proposals";
import {
  useEscalateProposalApiV1OrganizationsMeProposalsProposalIdEscalatePost,
} from "@/api/generated/escalations/escalations";
import { ApiError } from "@/api/mutator";

export default function ProposalDetailPage() {
  const params = useParams();
  const proposalId = Array.isArray(params?.proposalId)
    ? params.proposalId[0]
    : params?.proposalId;
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);

  const proposalQuery =
    useGetProposalApiV1OrganizationsMeProposalsProposalIdGet<any, ApiError>(
      proposalId!,
      { query: { enabled: Boolean(isSignedIn && proposalId) } },
    );

  const proposal =
    proposalQuery.data?.status === 200 ? proposalQuery.data.data : null;
  const requests = useMemo(
    () => proposal?.approval_requests ?? [],
    [proposal],
  );

  const approveMut =
    useApproveProposalApiV1OrganizationsMeProposalsProposalIdApprovePost<ApiError>(
      {
        mutation: {
          onSuccess: () => proposalQuery.refetch(),
        },
      },
    );
  const rejectMut =
    useRejectProposalApiV1OrganizationsMeProposalsProposalIdRejectPost<ApiError>(
      {
        mutation: {
          onSuccess: () => proposalQuery.refetch(),
        },
      },
    );
  const abstainMut =
    useAbstainProposalApiV1OrganizationsMeProposalsProposalIdAbstainPost<ApiError>(
      {
        mutation: {
          onSuccess: () => proposalQuery.refetch(),
        },
      },
    );

  const escalateMut =
    useEscalateProposalApiV1OrganizationsMeProposalsProposalIdEscalatePost<ApiError>(
      {
        mutation: {
          onSuccess: () => proposalQuery.refetch(),
        },
      },
    );

  const isVoting =
    approveMut.isPending || rejectMut.isPending || abstainMut.isPending;

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view proposal details.",
        forceRedirectUrl: `/proposals/${proposalId}`,
      }}
      title={proposal?.title ?? "Proposal Detail"}
      description={proposal?.description || undefined}
    >
      {proposal ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">
                Proposal Info
              </h3>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Status</dt>
                  <dd>
                    <StatusPill status={proposal.status} />
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Type</dt>
                  <dd className="text-slate-700">
                    {proposal.proposal_type?.replaceAll("_", " ")}
                  </dd>
                </div>
                {proposal.expires_at ? (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Expires</dt>
                    <dd className="text-slate-700">
                      {new Date(proposal.expires_at).toLocaleString()}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </div>

            {proposal.status === "pending_review" ? (
              <>
                <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h3 className="mb-3 text-sm font-semibold text-slate-800">
                    Cast Your Vote
                  </h3>
                  <VoteButton
                    onApprove={(rationale) =>
                      approveMut.mutate({
                        proposalId: proposalId!,
                        data: { rationale },
                      })
                    }
                    onReject={(rationale) =>
                      rejectMut.mutate({
                        proposalId: proposalId!,
                        data: { rationale },
                      })
                    }
                    onAbstain={(rationale) =>
                      abstainMut.mutate({
                        proposalId: proposalId!,
                        data: { rationale },
                      })
                    }
                    isLoading={isVoting}
                    disabled={isVoting}
                  />
                </div>

                <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h3 className="mb-3 text-sm font-semibold text-slate-800">
                    Escalate
                  </h3>
                  <p className="mb-3 text-xs text-slate-500">
                    Escalate this proposal to the parent zone for higher-level
                    review.
                  </p>
                  <EscalationDialog
                    onEscalate={(reason) =>
                      escalateMut.mutate({
                        proposalId: proposalId!,
                        data: { reason },
                      })
                    }
                    isLoading={escalateMut.isPending}
                    disabled={isVoting}
                  />
                </div>
              </>
            ) : null}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-4 text-sm font-semibold text-slate-800">
              Approval Progress
            </h3>
            <ApprovalStatusTracker requests={requests} />
          </div>
        </div>
      ) : proposalQuery.isLoading ? (
        <p className="text-sm text-slate-500">Loading...</p>
      ) : (
        <p className="text-sm text-red-500">Proposal not found.</p>
      )}
    </DashboardPageLayout>
  );
}
