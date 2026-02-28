/**
 * Client-side permission helpers for trust zone RBAC.
 */

export const ZONE_ROLE_PERMISSIONS: Record<string, Set<string>> = {
  executor: new Set(["zone.read", "zone.execute", "task.create", "task.update"]),
  approver: new Set([
    "zone.read",
    "proposal.review",
    "proposal.approve",
    "proposal.reject",
  ]),
  evaluator: new Set(["zone.read", "evaluation.create", "evaluation.submit"]),
  gardener: new Set([
    "zone.read",
    "zone.write",
    "proposal.review",
    "reviewer.select",
  ]),
};

export const ORG_ROLE_PERMISSIONS: Record<string, Set<string>> = {
  owner: new Set(["*"]),
  admin: new Set([
    "zone.read",
    "zone.write",
    "zone.create",
    "zone.delete",
    "proposal.create",
    "proposal.approve",
    "proposal.reject",
    "proposal.review",
    "evaluation.create",
    "evaluation.submit",
    "escalation.trigger",
    "reviewer.select",
    "task.create",
    "task.update",
    "zone.execute",
  ]),
  member: new Set(["zone.read", "proposal.create", "escalation.trigger"]),
};

export function hasOrgPermission(role: string, action: string): boolean {
  const perms = ORG_ROLE_PERMISSIONS[role];
  if (!perms) return false;
  return perms.has("*") || perms.has(action);
}

export function getZoneRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    executor: "Executor",
    approver: "Approver",
    evaluator: "Evaluator",
    gardener: "Gardener",
  };
  return labels[role] ?? role;
}
