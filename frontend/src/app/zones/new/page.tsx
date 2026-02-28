"use client";

export const dynamic = "force-dynamic";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/auth/clerk";
import { useOrganizationMembership } from "@/lib/use-organization-membership";
import { DashboardPageLayout } from "@/components/templates/DashboardPageLayout";
import { ZoneForm } from "@/components/zones/ZoneForm";
import {
  useCreateTrustZoneApiV1OrganizationsMeZonesPost,
  useListTrustZonesApiV1OrganizationsMeZonesGet,
  type listTrustZonesApiV1OrganizationsMeZonesGetResponse,
} from "@/api/generated/trust-zones/trust-zones";
import { ApiError } from "@/api/mutator";

export default function NewZonePage() {
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

  const zonesQuery = useListTrustZonesApiV1OrganizationsMeZonesGet<
    listTrustZonesApiV1OrganizationsMeZonesGetResponse,
    ApiError
  >(undefined, {
    query: { enabled: Boolean(isSignedIn) },
  });

  const parentZoneOptions = useMemo(
    () =>
      (zonesQuery.data?.status === 200 ? zonesQuery.data.data ?? [] : []).map(
        (z: any) => ({ id: z.id, name: z.name }),
      ),
    [zonesQuery.data],
  );

  const createMutation =
    useCreateTrustZoneApiV1OrganizationsMeZonesPost<ApiError>({
      mutation: {
        onSuccess: (result: any) => {
          if (result.status === 200) {
            router.push(`/zones/${result.data.id}`);
          }
        },
        onError: (err: ApiError) => {
          setError(err.message || "Something went wrong.");
        },
      },
    });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!isSignedIn || !name.trim()) return;
    setError(null);

    createMutation.mutate({
      data: {
        name: name.trim(),
        slug: slug.trim() || undefined,
        description,
        status,
        parent_zone_id: parentZoneId === "none" ? undefined : parentZoneId,
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
        message: "Sign in to create trust zones.",
        forceRedirectUrl: "/zones/new",
      }}
      title="Create Trust Zone"
      description="Define a new governance zone with delegation parameters"
      isAdmin={isAdmin}
      adminOnlyMessage="Only organization owners and admins can create root zones."
    >
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
        isLoading={createMutation.isPending}
        canSubmit={Boolean(name.trim())}
        cancelLabel="Cancel"
        submitLabel="Create zone"
        submitBusyLabel="Creating..."
        parentZoneOptions={parentZoneOptions}
        onSubmit={handleSubmit}
        onCancel={() => router.push("/zones")}
        onNameChange={setName}
        onSlugChange={setSlug}
        onDescriptionChange={setDescription}
        onStatusChange={setStatus}
        onParentZoneIdChange={setParentZoneId}
        onDecisionModelTypeChange={setDecisionModelType}
        onDecisionModelThresholdChange={setDecisionModelThreshold}
        onDecisionModelTimeoutHoursChange={setDecisionModelTimeoutHours}
      />
    </DashboardPageLayout>
  );
}
