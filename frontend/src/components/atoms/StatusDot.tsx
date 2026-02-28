import { cn } from "@/lib/utils";

type StatusDotVariant =
  | "agent"
  | "approval"
  | "task"
  | "zone"
  | "proposal"
  | "escalation"
  | "evaluation";

const AGENT_STATUS_DOT_CLASS_BY_STATUS: Record<string, string> = {
  online: "bg-emerald-500",
  busy: "bg-amber-500",
  provisioning: "bg-amber-500",
  updating: "bg-sky-500",
  deleting: "bg-rose-500",
  offline: "bg-slate-400",
};

const APPROVAL_STATUS_DOT_CLASS_BY_STATUS: Record<string, string> = {
  approved: "bg-emerald-500",
  rejected: "bg-rose-500",
  pending: "bg-amber-500",
};

const TASK_STATUS_DOT_CLASS_BY_STATUS: Record<string, string> = {
  inbox: "bg-slate-400",
  in_progress: "bg-purple-500",
  review: "bg-indigo-500",
  done: "bg-emerald-500",
};

const ZONE_STATUS_DOT_CLASS_BY_STATUS: Record<string, string> = {
  draft: "bg-slate-400",
  active: "bg-emerald-500",
  suspended: "bg-amber-500",
  archived: "bg-rose-400",
};

const PROPOSAL_STATUS_DOT_CLASS_BY_STATUS: Record<string, string> = {
  pending_review: "bg-amber-500",
  approved: "bg-emerald-500",
  rejected: "bg-rose-500",
  escalated: "bg-purple-500",
  expired: "bg-slate-400",
};

const ESCALATION_STATUS_DOT_CLASS_BY_STATUS: Record<string, string> = {
  pending: "bg-amber-500",
  accepted: "bg-emerald-500",
  dismissed: "bg-slate-400",
  resolved: "bg-sky-500",
};

const EVALUATION_STATUS_DOT_CLASS_BY_STATUS: Record<string, string> = {
  pending: "bg-amber-500",
  in_progress: "bg-purple-500",
  completed: "bg-emerald-500",
};

const STATUS_DOT_CLASS_BY_VARIANT: Record<
  StatusDotVariant,
  Record<string, string>
> = {
  agent: AGENT_STATUS_DOT_CLASS_BY_STATUS,
  approval: APPROVAL_STATUS_DOT_CLASS_BY_STATUS,
  task: TASK_STATUS_DOT_CLASS_BY_STATUS,
  zone: ZONE_STATUS_DOT_CLASS_BY_STATUS,
  proposal: PROPOSAL_STATUS_DOT_CLASS_BY_STATUS,
  escalation: ESCALATION_STATUS_DOT_CLASS_BY_STATUS,
  evaluation: EVALUATION_STATUS_DOT_CLASS_BY_STATUS,
};

const DEFAULT_STATUS_DOT_CLASS: Record<StatusDotVariant, string> = {
  agent: "bg-slate-300",
  approval: "bg-amber-500",
  task: "bg-slate-300",
  zone: "bg-slate-300",
  proposal: "bg-amber-500",
  escalation: "bg-amber-500",
  evaluation: "bg-slate-300",
};

export const statusDotClass = (
  status: string | null | undefined,
  variant: StatusDotVariant = "agent",
) => {
  const normalized = (status ?? "").trim().toLowerCase();
  if (!normalized) {
    return DEFAULT_STATUS_DOT_CLASS[variant];
  }
  return (
    STATUS_DOT_CLASS_BY_VARIANT[variant][normalized] ??
    DEFAULT_STATUS_DOT_CLASS[variant]
  );
};

type StatusDotProps = {
  status?: string | null;
  variant?: StatusDotVariant;
  className?: string;
};

export function StatusDot({
  status,
  variant = "agent",
  className,
}: StatusDotProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block h-2.5 w-2.5 rounded-full",
        statusDotClass(status, variant),
        className,
      )}
    />
  );
}
