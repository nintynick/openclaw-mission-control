import { Badge } from "@/components/ui/badge";

const ZONE_STATUS_STYLES: Record<
  string,
  "default" | "outline" | "accent" | "success" | "warning" | "danger"
> = {
  draft: "outline",
  active: "success",
  suspended: "warning",
  archived: "danger",
};

export function ZoneStatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={ZONE_STATUS_STYLES[status] ?? "default"}>
      {status.replaceAll("_", " ")}
    </Badge>
  );
}
