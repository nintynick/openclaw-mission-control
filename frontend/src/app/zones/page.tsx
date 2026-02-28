"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";
import Link from "next/link";

import { useAuth } from "@/auth/clerk";
import { useQueryClient } from "@tanstack/react-query";

import { ZonesTable } from "@/components/zones/ZonesTable";
import { ZoneTree } from "@/components/zones/ZoneTree";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { buttonVariants } from "@/components/ui/button";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { buildZoneTree } from "@/lib/zone-tree";
import {
  type listTrustZonesApiV1OrganizationsMeZonesGetResponse,
  useListTrustZonesApiV1OrganizationsMeZonesGet,
} from "@/api/generated/trust-zones/trust-zones";
import { ApiError } from "@/api/mutator";

export default function ZonesPage() {
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);
  const [viewMode, setViewMode] = useState<"table" | "tree">("table");

  const zonesQuery = useListTrustZonesApiV1OrganizationsMeZonesGet<
    listTrustZonesApiV1OrganizationsMeZonesGetResponse,
    ApiError
  >(undefined, {
    query: {
      enabled: Boolean(isSignedIn),
      refetchInterval: 30_000,
      refetchOnMount: "always",
    },
  });

  const zones = useMemo(
    () =>
      zonesQuery.data?.status === 200
        ? (zonesQuery.data.data ?? [])
        : [],
    [zonesQuery.data],
  );

  const treeNodes = useMemo(() => buildZoneTree(zones as any[]), [zones]);

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view trust zones.",
        forceRedirectUrl: "/zones",
      }}
      title="Trust Zones"
      description="Manage governance zones, delegation hierarchies, and RBAC"
      headerActions={
        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-lg border border-slate-200 bg-white">
            <button
              type="button"
              onClick={() => setViewMode("table")}
              className={`px-3 py-1.5 text-xs font-medium transition ${
                viewMode === "table"
                  ? "bg-slate-100 text-slate-800"
                  : "text-slate-500 hover:text-slate-700"
              } rounded-l-lg`}
            >
              Table
            </button>
            <button
              type="button"
              onClick={() => setViewMode("tree")}
              className={`px-3 py-1.5 text-xs font-medium transition ${
                viewMode === "tree"
                  ? "bg-slate-100 text-slate-800"
                  : "text-slate-500 hover:text-slate-700"
              } rounded-r-lg`}
            >
              Tree
            </button>
          </div>
          {isAdmin ? (
            <Link
              href="/zones/new"
              className={buttonVariants({ size: "md", variant: "primary" })}
            >
              Create zone
            </Link>
          ) : null}
        </div>
      }
      stickyHeader
    >
      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        {viewMode === "table" ? (
          <ZonesTable
            zones={zones as any[]}
            isLoading={zonesQuery.isLoading}
            showActions={isAdmin}
            stickyHeader
            emptyState={{
              title: "No trust zones yet",
              description:
                "Create your first trust zone to define governance boundaries and delegation hierarchies.",
              actionHref: "/zones/new",
              actionLabel: "Create your first zone",
            }}
          />
        ) : (
          <div className="p-4">
            <ZoneTree nodes={treeNodes as any[]} />
          </div>
        )}
      </div>

      {zonesQuery.error ? (
        <p className="mt-4 text-sm text-red-500">
          {zonesQuery.error.message}
        </p>
      ) : null}
    </DashboardPageLayout>
  );
}
