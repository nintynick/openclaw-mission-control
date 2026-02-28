"use client";

import Link from "next/link";

import { cn } from "@/lib/utils";
import { ZoneStatusBadge } from "./ZoneStatusBadge";

type ZoneTreeNode = {
  id: string;
  name: string;
  slug: string;
  status: string;
  children: ZoneTreeNode[];
};

function ZoneTreeItem({
  node,
  depth = 0,
}: {
  node: ZoneTreeNode;
  depth?: number;
}) {
  return (
    <li>
      <div
        className={cn(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm hover:bg-slate-50 transition",
          depth > 0 && "ml-6 border-l border-slate-200 pl-4",
        )}
      >
        <Link
          href={`/zones/${node.id}`}
          className="font-medium text-slate-800 hover:text-blue-700 transition"
        >
          {node.name}
        </Link>
        <span className="text-xs text-slate-400">{node.slug}</span>
        <ZoneStatusBadge status={node.status} />
      </div>
      {node.children.length > 0 ? (
        <ul className="space-y-0.5">
          {node.children.map((child) => (
            <ZoneTreeItem key={child.id} node={child} depth={depth + 1} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export function ZoneTree({ nodes }: { nodes: ZoneTreeNode[] }) {
  if (nodes.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-slate-500">
        No zones to display.
      </p>
    );
  }

  return (
    <ul className="space-y-1">
      {nodes.map((node) => (
        <ZoneTreeItem key={node.id} node={node} />
      ))}
    </ul>
  );
}
