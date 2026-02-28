import { Badge } from "@/components/ui/badge";

const STATUS_STYLES: Record<
  string,
  "default" | "outline" | "accent" | "success" | "warning" | "danger"
> = {
  inbox: "outline",
  assigned: "accent",
  in_progress: "warning",
  testing: "accent",
  review: "accent",
  done: "success",
  online: "success",
  busy: "warning",
  provisioning: "warning",
  offline: "outline",
  deleting: "danger",
  updating: "accent",
  // Zone statuses
  draft: "outline",
  active: "success",
  suspended: "warning",
  archived: "danger",
  // Proposal statuses
  pending_review: "warning",
  approved: "success",
  rejected: "danger",
  escalated: "accent",
  expired: "outline",
  // Escalation statuses
  pending: "warning",
  accepted: "success",
  dismissed: "outline",
  resolved: "accent",
  // Evaluation statuses
  completed: "success",
};

export function StatusPill({ status }: { status: string }) {
  return (
    <Badge variant={STATUS_STYLES[status] ?? "default"}>
      {status.replaceAll("_", " ")}
    </Badge>
  );
}
