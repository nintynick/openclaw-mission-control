"use client";

export const dynamic = "force-dynamic";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import { useAuth } from "@/auth/clerk";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { ZoneForm } from "@/components/zones/ZoneForm";
import {
  useGetTrustZoneApiV1OrganizationsMeZonesZoneIdGet,
  useUpdateTrustZoneApiV1OrganizationsMeZonesZoneIdPatch,
  useListTrustZonesApiV1OrganizationsMeZonesGet,
  type listTrustZonesApiV1OrganizationsMeZonesGetResponse,
} from "@/api/generated/trust-zones/trust-zones";
import { ApiError } from "@/api/mutator";

export default function EditZonePage() {
  const params = useParams();
  const zoneId = Array.isArray(params?.zoneId)
    ? params.zoneId[0]
    : params?.zoneId;
  const { isSignedIn } = useAuth();
  const router = useRouter();
  const { isAdmin } = useOrganizationMembership(isSignedIn);

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("draft");
  const [parentZoneId, setParentZoneId] = useState("none");
  const [decisionModelType, setDecisionModelType] = useState("threshold");
  const [decisionModelThreshold, setDecisionModelThreshold] = useState("1");
  const [decisionModelTimeoutHours, setDecisionModelTimeoutHours] =
    useState("48");
  const [error, setError] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  const zoneQuery = useGetTrustZoneApiV1OrganizationsMeZonesZoneIdGet<
    any,
    ApiError
  >(zoneId!, {
    query: { enabled: Boolean(isSignedIn && zoneId) },
  });

  const zonesQuery = useListTrustZonesApiV1OrganizationsMeZonesGet<
    listTrustZonesApiV1OrganizationsMeZonesGetResponse,
    ApiError
  >(undefined, {
    query: { enabled: Boolean(isSignedIn) },
  });

  const zone = zoneQuery.data?.status === 200 ? zoneQuery.data.data : null;

  useEffect(() => {
    if (zone && !initialized) {
      setName(zone.name ?? "");
      setSlug(zone.slug ?? "");
      setDescription(zone.description ?? "");
      setStatus(zone.status ?? "draft");
      setParentZoneId(zone.parent_zone_id ?? "none");
      if (zone.decision_model) {
        setDecisionModelType(zone.decision_model.model_type ?? "threshold");
        setDecisionModelThreshold(
          String(zone.decision_model.threshold ?? 1),
        );
        setDecisionModelTimeoutHours(
          String(zone.decision_model.timeout_hours ?? 48),
        );
      }
      setInitialized(true);
    }
  }, [zone, initialized]);

  const parentZoneOptions = useMemo(
    () =>
      (zonesQuery.data?.status === 200 ? zonesQuery.data.data ?? [] : [])
        .filter((z: any) => z.id !== zoneId)
        .map((z: any) => ({ id: z.id, name: z.name })),
    [zonesQuery.data, zoneId],
  );

  const updateMutation =
    useUpdateTrustZoneApiV1OrganizationsMeZonesZoneIdPatch<ApiError>({
      mutation: {
        onSuccess: () => {
          router.push(`/zones/${zoneId}`);
        },
        onError: (err: ApiError) => {
          setError(err.message || "Something went wrong.");
        },
      },
    });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isSignedIn || !zoneId || !name.trim()) return;
    setError(null);

    updateMutation.mutate({
      zoneId,
      data: {
        name: name.trim(),
        description,
        status,
        decision_model: {
          model_type: decisionModelType,
          threshold: parseInt(decisionModelThreshold, 10) || 1,
          timeout_hours: parseInt(decisionModelTimeoutHours, 10) || 48,
        },
      } as any,
    });
  };

  return (
    <DashboardPageLayout
      signedOut={{
        message: "Sign in to edit trust zones.",
        forceRedirectUrl: `/zones/${zoneId}/edit`,
      }}
      title={`Edit: ${zone?.name ?? "Zone"}`}
      isAdmin={isAdmin}
      adminOnlyMessage="Only organization owners and admins can edit zones."
    >
      {initialized ? (
        <ZoneForm
          name={name}
          slug={slug}
          description={description}
          status={status}
          parentZoneId={parentZoneId}
          decisionModelType={decisionModelType}
          decisionModelThreshold={decisionModelThreshold}
          decisionModelTimeoutHours={decisionModelTimeoutHours}
          errorMessage={error}
          isLoading={updateMutation.isPending}
          canSubmit={Boolean(name.trim())}
          cancelLabel="Cancel"
          submitLabel="Save changes"
          submitBusyLabel="Saving..."
          parentZoneOptions={parentZoneOptions}
          onSubmit={handleSubmit}
          onCancel={() => router.push(`/zones/${zoneId}`)}
          onNameChange={setName}
          onSlugChange={setSlug}
          onDescriptionChange={setDescription}
          onStatusChange={setStatus}
          onParentZoneIdChange={setParentZoneId}
          onDecisionModelTypeChange={setDecisionModelType}
          onDecisionModelThresholdChange={setDecisionModelThreshold}
          onDecisionModelTimeoutHoursChange={setDecisionModelTimeoutHours}
        />
      ) : zoneQuery.isLoading ? (
        <p className="text-sm text-slate-500">Loading zone...</p>
      ) : (
        <p className="text-sm text-red-500">Zone not found.</p>
      )}
    </DashboardPageLayout>
  );
}
