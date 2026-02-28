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
import { ZoneStatusBadge } from "@/components/zones/ZoneStatusBadge";
import { linkifyCell, dateCell } from "@/components/tables/cell-formatters";

type TrustZoneRow = {
  id: string;
  name: string;
  slug: string;
  status: string;
  description: string;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
};

type ZonesTableProps = {
  zones: TrustZoneRow[];
  isLoading?: boolean;
  sorting?: SortingState;
  onSortingChange?: OnChangeFn<SortingState>;
  stickyHeader?: boolean;
  showActions?: boolean;
  onDelete?: (zone: TrustZoneRow) => void;
  emptyMessage?: string;
  emptyState?: Omit<DataTableEmptyState, "icon"> & {
    icon?: DataTableEmptyState["icon"];
  };
};

export function ZonesTable({
  zones,
  isLoading,
  sorting,
  onSortingChange,
  stickyHeader,
  showActions,
  onDelete,
  emptyState,
}: ZonesTableProps) {
  const [internalSorting, setInternalSorting] = useState<SortingState>([
    { id: "name", desc: false },
  ]);
  const resolvedSorting = sorting ?? internalSorting;
  const resolvedOnSortingChange = onSortingChange ?? setInternalSorting;

  const columns = useMemo<ColumnDef<TrustZoneRow>[]>(
    () => [
      {
        accessorKey: "name",
        header: "Zone",
        cell: ({ row }) =>
          linkifyCell({
            href: `/zones/${row.original.id}`,
            label: row.original.name,
            subtitle: row.original.slug,
          }),
      },
      {
        accessorKey: "status",
        header: "Status",
        cell: ({ row }) => <ZoneStatusBadge status={row.original.status} />,
        enableSorting: false,
      },
      {
        accessorKey: "description",
        header: "Description",
        cell: ({ row }) => (
          <span className="text-sm text-slate-600">
            {row.original.description
              ? row.original.description.length > 60
                ? `${row.original.description.slice(0, 60)}...`
                : row.original.description
              : "\u2014"}
          </span>
        ),
        enableSorting: false,
      },
      {
        accessorKey: "updated_at",
        header: "Updated",
        cell: ({ row }) => dateCell(row.original.updated_at),
      },
    ],
    [],
  );

  const table = useReactTable({
    data: zones,
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
      rowActions={
        showActions
          ? {
              getEditHref: (zone) => `/zones/${zone.id}/edit`,
              onDelete,
            }
          : undefined
      }
      emptyState={emptyState}
    />
  );
}
