/**
 * Decision model type labels and defaults for trust zone configuration.
 */

export const DECISION_MODEL_TYPES = [
  {
    value: "unilateral",
    label: "Unilateral",
    description: "First reviewer vote decides the outcome.",
  },
  {
    value: "threshold",
    label: "Threshold",
    description: "Requires a minimum number of approvals (k-of-n).",
  },
  {
    value: "majority",
    label: "Majority",
    description: "Requires more than 50% approval votes.",
  },
  {
    value: "weighted",
    label: "Weighted",
    description: "Role-weighted scoring determines the outcome.",
  },
  {
    value: "consensus",
    label: "Consensus with Timeout",
    description:
      "All reviewers must approve, or falls back to threshold after timeout.",
  },
] as const;

export type DecisionModelType = (typeof DECISION_MODEL_TYPES)[number]["value"];

export function getDecisionModelLabel(type: string): string {
  return (
    DECISION_MODEL_TYPES.find((t) => t.value === type)?.label ?? type
  );
}

export function getDefaultDecisionModel(): {
  model_type: DecisionModelType;
  threshold: number;
  timeout_hours: number;
} {
  return {
    model_type: "threshold",
    threshold: 1,
    timeout_hours: 48,
  };
}
