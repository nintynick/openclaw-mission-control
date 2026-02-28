"use client";

import { cn } from "@/lib/utils";
import { formatRelativeTimestamp } from "@/lib/formatters";

type ApprovalRequestEntry = {
  id: string;
  reviewer_id: string;
  reviewer_type: string;
  selection_reason: string;
  decision: string | null;
  rationale: string;
  decided_at: string | null;
  created_at: string;
};

export function ApprovalStatusTracker({
  requests,
}: {
  requests: ApprovalRequestEntry[];
}) {
  if (requests.length === 0) {
    return (
      <p className="text-sm text-slate-500">No reviewers assigned yet.</p>
    );
  }

  return (
    <div className="space-y-0">
      {requests.map((request, index) => (
        <div key={request.id} className="flex gap-3">
          <div className="flex flex-col items-center">
            <div
              className={cn(
                "h-3 w-3 rounded-full mt-1.5",
                request.decision === "approve" && "bg-emerald-500",
                request.decision === "reject" && "bg-rose-500",
                request.decision === "abstain" && "bg-slate-400",
                request.decision === null && "bg-amber-400 ring-2 ring-amber-100",
              )}
            />
            {index < requests.length - 1 ? (
              <div className="w-0.5 flex-1 bg-slate-200" />
            ) : null}
          </div>
          <div className="pb-4">
            <p className="text-sm font-medium text-slate-700">
              Reviewer {String(request.reviewer_id).slice(0, 8)}...
              <span className="ml-2 text-xs font-normal text-slate-400">
                {request.reviewer_type}
              </span>
            </p>
            {request.decision ? (
              <p className="mt-0.5 text-xs text-slate-600">
                <span
                  className={cn(
                    "font-medium",
                    request.decision === "approve" && "text-emerald-600",
                    request.decision === "reject" && "text-rose-600",
                    request.decision === "abstain" && "text-slate-500",
                  )}
                >
                  {request.decision}
                </span>
                {request.rationale ? ` — ${request.rationale}` : ""}
              </p>
            ) : (
              <p className="mt-0.5 text-xs text-amber-600">Pending review</p>
            )}
            {request.decided_at ? (
              <p className="mt-0.5 text-xs text-slate-400">
                {formatRelativeTimestamp(request.decided_at)}
              </p>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}
