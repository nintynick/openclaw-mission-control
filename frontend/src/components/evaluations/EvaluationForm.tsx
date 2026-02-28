"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type EvaluationFormProps = {
  onSubmit: (criterion: string, score: number, rationale: string) => void;
  isLoading: boolean;
  disabled?: boolean;
  criteria?: string[];
};

const DEFAULT_CRITERIA = [
  "quality",
  "timeliness",
  "alignment",
  "communication",
];

export function EvaluationForm({
  onSubmit,
  isLoading,
  disabled,
  criteria = DEFAULT_CRITERIA,
}: EvaluationFormProps) {
  const [selectedCriterion, setSelectedCriterion] = useState(criteria[0] ?? "quality");
  const [score, setScore] = useState(0.8);
  const [rationale, setRationale] = useState("");

  const handleSubmit = () => {
    onSubmit(selectedCriterion, score, rationale);
    setRationale("");
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">
          Criterion
        </label>
        <div className="flex flex-wrap gap-2">
          {criteria.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setSelectedCriterion(c)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                selectedCriterion === c
                  ? "bg-slate-800 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">
          Score ({(score * 100).toFixed(0)}%)
        </label>
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={score}
          onChange={(e) => setScore(parseFloat(e.target.value))}
          className="w-full"
        />
        <div className="mt-1 flex justify-between text-xs text-slate-400">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-medium text-slate-600">
          Rationale
        </label>
        <Textarea
          value={rationale}
          onChange={(e) => setRationale(e.target.value)}
          placeholder="Explain your score..."
          rows={2}
        />
      </div>

      <Button
        variant="primary"
        size="sm"
        onClick={handleSubmit}
        disabled={disabled || isLoading}
      >
        {isLoading ? "Submitting..." : "Submit Score"}
      </Button>
    </div>
  );
}
