"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type EscalationDialogProps = {
  onEscalate: (reason: string) => void;
  isLoading: boolean;
  disabled?: boolean;
  type?: "action" | "governance";
};

export function EscalationDialog({
  onEscalate,
  isLoading,
  disabled,
  type = "action",
}: EscalationDialogProps) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");

  const handleSubmit = () => {
    onEscalate(reason);
    setReason("");
    setOpen(false);
  };

  if (!open) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(true)}
        disabled={disabled || isLoading}
        className="text-amber-600 border-amber-200 hover:bg-amber-50"
      >
        {type === "governance" ? "Escalate Governance" : "Escalate"}
      </Button>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p className="text-sm font-medium text-amber-800">
        {type === "governance"
          ? "Escalate a governance concern to the parent zone"
          : "Escalate this proposal to the parent zone for review"}
      </p>
      <Textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason for escalation..."
        rows={2}
      />
      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={handleSubmit}
          disabled={isLoading}
        >
          {isLoading ? "Escalating..." : "Confirm Escalation"}
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setOpen(false);
            setReason("");
          }}
          disabled={isLoading}
        >
          Cancel
        </Button>
      </div>
    </div>
  );
}
