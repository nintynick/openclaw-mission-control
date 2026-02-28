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

type ProposalRow = {
  id: string;
  title: string;
  proposal_type: string;
  status: string;
  created_at: string;
  [key: string]: unknown;
};

type ProposalsTableProps = {
  proposals: ProposalRow[];
  isLoading?: boolean;
  sorting?: SortingState;
  onSortingChange?: OnChangeFn<SortingState>;
  stickyHeader?: boolean;
  emptyState?: Omit<DataTableEmptyState, "icon"> & {
    icon?: DataTableEmptyState["icon"];
  };
};

export function ProposalsTable({
  proposals,
  isLoading,
  sorting,
  onSortingChange,
  stickyHeader,
  emptyState,
}: ProposalsTableProps) {
  const [internalSorting, setInternalSorting] = useState<SortingState>([
    { id: "created_at", desc: true },
  ]);
  const resolvedSorting = sorting ?? internalSorting;
  const resolvedOnSortingChange = onSortingChange ?? setInternalSorting;

  const columns = useMemo<ColumnDef<ProposalRow>[]>(
    () => [
      {
        accessorKey: "title",
        header: "Proposal",
        cell: ({ row }) =>
          linkifyCell({
            href: `/proposals/${row.original.id}`,
            label: row.original.title,
            subtitle: row.original.proposal_type.replaceAll("_", " "),
          }),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <StatusPill status={row.original.status} />,
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
    data: proposals,
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
