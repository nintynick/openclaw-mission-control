"use client";

import { useMemo, useState } from "react";
import type { ColumnDef, OnChangeFn, SortingState } from "@tanstack/react-table";
import {
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import { DataTable } from "@/components/tables/DataTable";
import type { DataTableEmptyState } from "@/components/tables/DataTable";
import { StatusPill } from "@/components/atoms/StatusPill";
import { linkifyCell, dateCell } from "@/components/tables/cell-formatters";

type EscalationRow = {
  id: string;
  escalation_type: string;
  reason: string;
  status: string;
  source_zone_id: string;
  target_zone_id: string;
  created_at: string;
  [key: string]: unknown;
};

type EscalationsTableProps = {
  escalations: EscalationRow[];
  isLoading?: boolean;
  sorting?: SortingState;
  onSortingChange?: OnChangeFn<SortingState>;
  stickyHeader?: boolean;
  emptyState?: Omit<DataTableEmptyState, "icon"> & {
    icon?: DataTableEmptyState["icon"];
  };
};

export function EscalationsTable({
  escalations,
  isLoading,
  sorting,
  onSortingChange,
  stickyHeader,
  emptyState,
}: EscalationsTableProps) {
  const [internalSorting, setInternalSorting] = useState<SortingState>([
    { id: "created_at", desc: true },
  ]);
  const resolvedSorting = sorting ?? internalSorting;
  const resolvedOnSortingChange = onSortingChange ?? setInternalSorting;

  const columns = useMemo<ColumnDef<EscalationRow>[]>(
    () => [
      {
        accessorKey: "reason",
        header: "Escalation",
        cell: ({ row }) =>
          linkifyCell({
            href: `/escalations/${row.original.id}`,
            label: row.original.reason || "No reason provided",
            subtitle: row.original.escalation_type.replaceAll("_", " "),
          }),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusPill status={row.original.status} />,
        enableSorting: false,
      },
      {
        accessorKey: "escalation_type",
        header: "Type",
        cell: ({ row }) => (
          <span className="text-sm capitalize text-slate-700">
            {row.original.escalation_type}
          </span>
        ),
        enableSorting: false,
      },
      {
        accessorKey: "created_at",
        header: "Created",
        cell: ({ row }) => dateCell(row.original.created_at),
      },
    ],
    [],
  );

  const table = useReactTable({
    data: escalations,
    columns,
    enableSorting: true,
    state: { sorting: resolvedSorting },
    onSortingChange: resolvedOnSortingChange,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <DataTable
      table={table}
      isLoading={isLoading}
      stickyHeader={stickyHeader}
      emptyState={emptyState}
    />
  );
}
