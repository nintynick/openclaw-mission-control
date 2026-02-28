"use client";

import type { FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DecisionModelBuilder } from "./DecisionModelBuilder";

type ZoneFormProps = {
  name: string;
  slug: string;
  description: string;
  status: string;
  parentZoneId: string;
  decisionModelType: string;
  decisionModelThreshold: string;
  decisionModelTimeoutHours: string;
  errorMessage: string | null;
  isLoading: boolean;
  canSubmit: boolean;
  cancelLabel: string;
  submitLabel: string;
  submitBusyLabel: string;
  parentZoneOptions: { id: string; name: string }[];
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
  onNameChange: (value: string) => void;
  onSlugChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onParentZoneIdChange: (value: string) => void;
  onDecisionModelTypeChange: (value: string) => void;
  onDecisionModelThresholdChange: (value: string) => void;
  onDecisionModelTimeoutHoursChange: (value: string) => void;
};

export function ZoneForm({
  name,
  slug,
  description,
  status,
  parentZoneId,
  decisionModelType,
  decisionModelThreshold,
  decisionModelTimeoutHours,
  errorMessage,
  isLoading,
  canSubmit,
  cancelLabel,
  submitLabel,
  submitBusyLabel,
  parentZoneOptions,
  onSubmit,
  onCancel,
  onNameChange,
  onSlugChange,
  onDescriptionChange,
  onStatusChange,
  onParentZoneIdChange,
  onDecisionModelTypeChange,
  onDecisionModelThresholdChange,
  onDecisionModelTimeoutHoursChange,
}: ZoneFormProps) {
  return (
    <form
      onSubmit={onSubmit}
      className="space-y-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="zone-name">Name</Label>
          <Input
            id="zone-name"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="e.g. Engineering"
            required
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="zone-slug">Slug</Label>
          <Input
            id="zone-slug"
            value={slug}
            onChange={(e) => onSlugChange(e.target.value)}
            placeholder="Auto-generated from name"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="zone-description">Description</Label>
        <Textarea
          id="zone-description"
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          placeholder="Describe this zone's purpose and responsibilities..."
          rows={3}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="zone-status">Status</Label>
          <Select value={status} onValueChange={onStatusChange}>
            <SelectTrigger id="zone-status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="suspended">Suspended</SelectItem>
              <SelectItem value="archived">Archived</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="zone-parent">Parent Zone</Label>
          <Select value={parentZoneId} onValueChange={onParentZoneIdChange}>
            <SelectTrigger id="zone-parent">
              <SelectValue placeholder="None (root zone)" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">None (root zone)</SelectItem>
              {parentZoneOptions.map((zone) => (
                <SelectItem key={zone.id} value={zone.id}>
                  {zone.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <DecisionModelBuilder
        modelType={decisionModelType}
        threshold={decisionModelThreshold}
        timeoutHours={decisionModelTimeoutHours}
        onModelTypeChange={onDecisionModelTypeChange}
        onThresholdChange={onDecisionModelThresholdChange}
        onTimeoutHoursChange={onDecisionModelTimeoutHoursChange}
      />

      {errorMessage ? (
        <p className="text-xs text-red-500">{errorMessage}</p>
      ) : null}

      <div className="flex items-center justify-end gap-3">
        <Button type="button" variant="ghost" onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button type="submit" variant="primary" disabled={!canSubmit || isLoading}>
          {isLoading ? submitBusyLabel : submitLabel}
        </Button>
      </div>
    </form>
  );
}
