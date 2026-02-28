"use client";

import { Button } from "@/components/ui/button";

type EscalationCosignDialogProps = {
  onCosign: () => void;
  isLoading: boolean;
  disabled?: boolean;
  cosignerCount: number;
  requiredCosigners?: number;
};

export function EscalationCosignDialog({
  onCosign,
  isLoading,
  disabled,
  cosignerCount,
  requiredCosigners = 2,
}: EscalationCosignDialogProps) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-sm font-medium text-slate-800">Co-sign this escalation</p>
      <p className="mt-1 text-xs text-slate-500">
        {cosignerCount} of {requiredCosigners} co-signers needed to activate
      </p>
      <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="bg-amber-500 transition-all"
          style={{
            width: `${Math.min(100, (cosignerCount / requiredCosigners) * 100)}%`,
          }}
        />
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={onCosign}
        disabled={disabled || isLoading}
        className="mt-3"
      >
        {isLoading ? "Co-signing..." : "Co-sign"}
      </Button>
    </div>
  );
}
