"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type VoteButtonProps = {
  onApprove: (rationale: string) => void;
  onReject: (rationale: string) => void;
  onAbstain: (rationale: string) => void;
  isLoading: boolean;
  disabled: boolean;
};

export function VoteButton({
  onApprove,
  onReject,
  onAbstain,
  isLoading,
  disabled,
}: VoteButtonProps) {
  const [rationale, setRationale] = useState("");

  return (
    <div className="space-y-3">
      <Textarea
        value={rationale}
        onChange={(e) => setRationale(e.target.value)}
        placeholder="Optional rationale for your vote..."
        rows={2}
      />
      <div className="flex items-center gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={() => onApprove(rationale)}
          disabled={disabled || isLoading}
        >
          Approve
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onReject(rationale)}
          disabled={disabled || isLoading}
          className="text-rose-600 border-rose-200 hover:bg-rose-50"
        >
          Reject
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onAbstain(rationale)}
          disabled={disabled || isLoading}
        >
          Abstain
        </Button>
      </div>
    </div>
  );
}
