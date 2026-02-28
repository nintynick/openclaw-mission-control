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

type EvaluationRow = {
  id: string;
  zone_id: string;
  executor_id: string;
  status: string;
  aggregate_result: { overall_score?: number } | null;
  created_at: string;
  [key: string]: unknown;
};

type EvaluationsTableProps = {
  evaluations: EvaluationRow[];
  isLoading?: boolean;
  sorting?: SortingState;
  onSortingChange?: OnChangeFn<SortingState>;
  stickyHeader?: boolean;
  emptyState?: Omit<DataTableEmptyState, "icon"> & {
    icon?: DataTableEmptyState["icon"];
  };
};

export function EvaluationsTable({
  evaluations,
  isLoading,
  sorting,
  onSortingChange,
  stickyHeader,
  emptyState,
}: EvaluationsTableProps) {
  const [internalSorting, setInternalSorting] = useState<SortingState>([
    { id: "created_at", desc: true },
  ]);
  const resolvedSorting = sorting ?? internalSorting;
  const resolvedOnSortingChange = onSortingChange ?? setInternalSorting;

  const columns = useMemo<ColumnDef<EvaluationRow>[]>(
    () => [
      {
        accessorKey: "id",
        header: "Evaluation",
        cell: ({ row }) =>
          linkifyCell({
            href: `/evaluations/${row.original.id}`,
            label: `Evaluation ${String(row.original.id).slice(0, 8)}...`,
            subtitle: `Executor ${String(row.original.executor_id).slice(0, 8)}...`,
          }),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusPill status={row.original.status} />,
        enableSorting: false,
      },
      {
        id: "score",
        header: "Score",
        cell: ({ row }) => {
          const score = row.original.aggregate_result?.overall_score;
          if (score == null) {
            return <span className="text-sm text-slate-400">—</span>;
          }
          return (
            <span className="text-sm font-medium text-slate-700">
              {(score * 100).toFixed(0)}%
            </span>
          );
        },
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
    data: evaluations,
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
