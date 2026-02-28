/**
 * Build a nested tree structure from a flat list of trust zones.
 */

export type ZoneNode = {
  id: string;
  name: string;
  slug: string;
  status: string;
  description: string;
  parent_zone_id: string | null;
  children: ZoneNode[];
  [key: string]: unknown;
};

export function buildZoneTree<
  T extends { id: string; parent_zone_id?: string | null },
>(zones: T[]): (T & { children: (T & { children: unknown[] })[] })[] {
  const map = new Map<string, T & { children: (T & { children: unknown[] })[] }>();
  const roots: (T & { children: (T & { children: unknown[] })[] })[] = [];

  for (const zone of zones) {
    map.set(zone.id, { ...zone, children: [] });
  }

  for (const zone of zones) {
    const node = map.get(zone.id)!;
    if (zone.parent_zone_id && map.has(zone.parent_zone_id)) {
      map.get(zone.parent_zone_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}
