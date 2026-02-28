"use client";

export const dynamic = "force-dynamic";

import { useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { useAuth } from "@/auth/clerk";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { ZoneStatusBadge } from "@/components/zones/ZoneStatusBadge";
import { buttonVariants } from "@/components/ui/button";
import { getDecisionModelLabel } from "@/lib/decision-model";
import { getZoneRoleLabel } from "@/lib/permissions";
import {
  useGetTrustZoneApiV1OrganizationsMeZonesZoneIdGet,
  useListZoneAssignmentsApiV1OrganizationsMeZonesZoneIdAssignmentsGet,
  useListZoneChildrenApiV1OrganizationsMeZonesZoneIdChildrenGet,
} from "@/api/generated/trust-zones/trust-zones";
import { ApiError } from "@/api/mutator";

export default function ZoneDetailPage() {
  const params = useParams();
  const zoneId = Array.isArray(params?.zoneId)
    ? params.zoneId[0]
    : params?.zoneId;
  const { isSignedIn } = useAuth();
  const { isAdmin } = useOrganizationMembership(isSignedIn);

  const zoneQuery = useGetTrustZoneApiV1OrganizationsMeZonesZoneIdGet<
    any,
    ApiError
  >(zoneId!, {
    query: { enabled: Boolean(isSignedIn && zoneId) },
  });

  const assignmentsQuery =
    useListZoneAssignmentsApiV1OrganizationsMeZonesZoneIdAssignmentsGet<
      any,
      ApiError
    >(zoneId!, {
      query: { enabled: Boolean(isSignedIn && zoneId) },
    });

  const childrenQuery =
    useListZoneChildrenApiV1OrganizationsMeZonesZoneIdChildrenGet<
      any,
      ApiError
    >(zoneId!, {
      query: { enabled: Boolean(isSignedIn && zoneId) },
    });

  const zone = zoneQuery.data?.status === 200 ? zoneQuery.data.data : null;
  const assignments = useMemo(
    () =>
      assignmentsQuery.data?.status === 200
        ? assignmentsQuery.data.data ?? []
        : [],
    [assignmentsQuery.data],
  );
  const children = useMemo(
    () =>
      childrenQuery.data?.status === 200
        ? childrenQuery.data.data ?? []
        : [],
    [childrenQuery.data],
  );

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to view zone details.",
        forceRedirectUrl: `/zones/${zoneId}`,
      }}
      title={zone?.name ?? "Zone Detail"}
      description={zone?.description || undefined}
      headerActions={
        isAdmin && zone ? (
          <Link
            href={`/zones/${zoneId}/edit`}
            className={buttonVariants({ size: "md", variant: "secondary" })}
          >
            Edit zone
          </Link>
        ) : null
      }
    >
      {zone ? (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Left column: Zone metadata */}
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">Details</h3>
              <dl className="mt-4 space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-slate-500">Status</dt>
                  <dd>
                    <ZoneStatusBadge status={zone.status} />
                  </dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-slate-500">Slug</dt>
                  <dd className="font-mono text-slate-700">{zone.slug}</dd>
                </div>
                {zone.decision_model ? (
                  <div className="flex justify-between">
                    <dt className="text-slate-500">Decision Model</dt>
                    <dd className="text-slate-700">
                      {getDecisionModelLabel(
                        zone.decision_model.model_type ?? "",
                      )}
                    </dd>
                  </div>
                ) : null}
              </dl>
            </div>

            {children.length > 0 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-sm font-semibold text-slate-800">
                  Child Zones ({children.length})
                </h3>
                <ul className="mt-3 space-y-2">
                  {children.map((child: any) => (
                    <li key={child.id}>
                      <Link
                        href={`/zones/${child.id}`}
                        className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition"
                      >
                        <span className="font-medium">{child.name}</span>
                        <ZoneStatusBadge status={child.status} />
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>

          {/* Right column: Assignments */}
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="text-sm font-semibold text-slate-800">
                Assignments ({assignments.length})
              </h3>
              {assignments.length > 0 ? (
                <ul className="mt-3 divide-y divide-slate-100">
                  {assignments.map((a: any) => (
                    <li
                      key={a.id}
                      className="flex items-center justify-between py-2.5"
                    >
                      <span className="text-sm text-slate-700">
                        Member {String(a.member_id).slice(0, 8)}...
                      </span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                        {getZoneRoleLabel(a.role)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-3 text-sm text-slate-500">
                  No members assigned to this zone yet.
                </p>
              )}
            </div>
          </div>
        </div>
      ) : zoneQuery.isLoading ? (
        <p className="text-sm text-slate-500">Loading...</p>
      ) : (
        <p className="text-sm text-red-500">Zone not found.</p>
      )}
    </DashboardPageLayout>
  );
}
