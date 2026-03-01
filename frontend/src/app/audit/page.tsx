"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";

import { useAuth } from "@/auth/clerk";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { useListAuditEntriesApiV1OrganizationsMeAuditGet } from "@/api/generated/audit/audit";
import { ApiError } from "@/api/mutator";

function truncateId(id: string) {
  return id.length > 8 ? `${id.slice(0, 8)}...` : id;
}

function formatTimestamp(ts: string) {
  return new Date(ts).toLocaleString();
}

const ACTION_FILTERS = [
  "all",
  "zone.create",
  "zone.update",
  "zone.archive",
  "zone.suspend",
  "proposal.create",
  "proposal.approve",
  "proposal.reject",
  "evaluation.create",
  "evaluation.finalize",
  "escalation.create",
  "escalation.resolve",
] as const;

export default function AuditPage() {
  const { isSignedIn } = useAuth();
  const [actionFilter, setActionFilter] = useState<string>("all");

  const auditQuery = useListAuditEntriesApiV1OrganizationsMeAuditGet<
    any,
    ApiError
  >(
    actionFilter !== "all" ? { action: actionFilter } : undefined,
    {
      query: { enabled: Boolean(isSignedIn) },
    },
  );

  const entries = useMemo(
    () =>
      auditQuery.data?.status === 200 ? auditQuery.data.data ?? [] : [],
    [auditQuery.data],
  );

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view the audit trail.",
        forceRedirectUrl: "/audit",
      }}
      title="Audit Trail"
      description="Governance actions and changes across the organization."
    >
      <div className="space-y-4">
        {/* Filter */}
        <div className="flex items-center gap-2">
          <label
            htmlFor="action-filter"
            className="text-sm font-medium text-slate-600"
          >
            Action:
          </label>
          <select
            id="action-filter"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm focus:border-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-300"
          >
            {ACTION_FILTERS.map((action) => (
              <option key={action} value={action}>
                {action === "all" ? "All actions" : action}
              </option>
            ))}
          </select>
        </div>

        {/* Table */}
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
          {auditQuery.isLoading ? (
            <p className="p-6 text-sm text-slate-500">Loading...</p>
          ) : entries.length === 0 ? (
            <p className="p-6 text-sm text-slate-500">No audit entries found.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs font-medium text-slate-500">
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Actor Type</th>
                    <th className="px-4 py-3">Actor ID</th>
                    <th className="px-4 py-3">Target Type</th>
                    <th className="px-4 py-3">Target ID</th>
                    <th className="px-4 py-3">Zone ID</th>
                    <th className="px-4 py-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {entries.map((entry: any) => (
                    <tr key={entry.id} className="hover:bg-slate-50">
                      <td className="px-4 py-3">
                        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
                          {entry.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {entry.actor_type}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-700">
                        {truncateId(entry.actor_id)}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {entry.target_type}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-700">
                        {entry.target_id ? truncateId(entry.target_id) : "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-700">
                        {entry.zone_id ? truncateId(entry.zone_id) : "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {formatTimestamp(entry.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </DashboardPageLayout>
  );
}
