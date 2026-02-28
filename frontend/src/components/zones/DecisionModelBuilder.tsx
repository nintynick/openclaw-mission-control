"use client";

import { DECISION_MODEL_TYPES } from "@/lib/decision-model";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type DecisionModelBuilderProps = {
  modelType: string;
  threshold: string;
  timeoutHours: string;
  onModelTypeChange: (value: string) => void;
  onThresholdChange: (value: string) => void;
  onTimeoutHoursChange: (value: string) => void;
};

export function DecisionModelBuilder({
  modelType,
  threshold,
  timeoutHours,
  onModelTypeChange,
  onThresholdChange,
  onTimeoutHoursChange,
}: DecisionModelBuilderProps) {
  return (
    <div className="space-y-4">
      <Label>Decision Model</Label>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {DECISION_MODEL_TYPES.map((type) => (
          <button
            key={type.value}
            type="button"
            onClick={() => onModelTypeChange(type.value)}
            className={cn(
              "rounded-xl border p-4 text-left transition",
              modelType === type.value
                ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500"
                : "border-slate-200 hover:border-slate-300",
            )}
          >
            <p className="text-sm font-medium text-slate-800">{type.label}</p>
            <p className="mt-1 text-xs text-slate-500">{type.description}</p>
          </button>
        ))}
      </div>

      {(modelType === "threshold" || modelType === "consensus") && (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="dm-threshold">
              {modelType === "consensus"
                ? "Fallback Threshold"
                : "Required Approvals"}
            </Label>
            <Input
              id="dm-threshold"
              type="number"
              min="1"
              value={threshold}
              onChange={(e) => onThresholdChange(e.target.value)}
            />
          </div>
          {modelType === "consensus" && (
            <div className="space-y-2">
              <Label htmlFor="dm-timeout">Timeout (hours)</Label>
              <Input
                id="dm-timeout"
                type="number"
                min="1"
                value={timeoutHours}
                onChange={(e) => onTimeoutHoursChange(e.target.value)}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
