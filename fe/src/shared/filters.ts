import type { FeaturedAxis, MgmtLevel, Site, UserCoords } from "./types";
import { haversineKm } from "./geo";

/**
 * Concept-shaped filter slots — these are unioned and sent as repeated
 * `concept=<id>` params (server-side AND). Backend matches by concept ID
 * (English, e.g. "valley", "mountainview", "swimmingpool"), NOT the
 * Korean display name.
 *
 * Origin: fe/index.legacy.html:150-153.
 */
export const CONCEPT_FILTER_KEYS = [
  "conceptAxis",
  "view",
  "facility",
  "kidsFacility",
  "surface",
  "space",
  "parking",
  "audience",
  "vibe",
] as const;

export type ConceptFilterKey = (typeof CONCEPT_FILTER_KEYS)[number];

/**
 * Stable string for useEffect deps (Set identity changes every render).
 *
 * Origin: fe/index.legacy.html:155-159.
 */
export function setSerialize(set: Set<string> | undefined): string {
  if (!set || set.size === 0) return "";
  return [...set].sort().join("|");
}

/**
 * App-level filter state. Concept slots (CONCEPT_FILTER_KEYS) are server-
 * routed; the rest are client-side because the backend doesn't index
 * them. Boolean `has_<axis>` toggles are stored as a flat
 * `Record<string, boolean>` keyed by `has_${axisId}` (matches the row
 * column shape).
 */
export interface Filters {
  region: Set<string>;
  conceptAxis: Set<string>;
  view: Set<string>;
  facility: Set<string>;
  kidsFacility: Set<string>;
  surface: Set<string>;
  space: Set<string>;
  parking: Set<string>;
  audience: Set<string>;
  vibe: Set<string>;
  /** Terrain (server `r.location_types`). */
  terrain: Set<string>;
  /** Curated collection name set. */
  collection: Set<string>;
  /** Raw facility tags (server `r.facilities`). */
  facilityRaw: Set<string>;
  /** Management mark levels (bib/recommended/notable/exceptional). */
  management: Set<MgmtLevel>;
  /** Featured-axis booleans, keyed `has_<axisId>`. */
  [hasKey: `has_${string}`]: boolean | Set<string> | undefined;
}

/**
 * Optional ETA + user-location overlay applied on top of the client-side
 * filter pass. When both are set, ETA filters first then haversine-sort
 * by distance from `userLoc`.
 */
export interface VisibleRowsOpts {
  featuredAxes?: FeaturedAxis[];
  managementCampLevels?: Map<string, MgmtLevel> | null;
  /** Per-camp ETA results keyed by camp id. */
  etaMap?: Record<string, { within?: boolean }> | null;
  /** When true, hide camps whose ETA is out of range. */
  etaActive?: boolean;
  /** When set, attach `_distanceKm` and sort closest-first. */
  userLoc?: UserCoords | null;
}

/**
 * Client-side filter + ETA + distance-sort pipeline. Mirrors the
 * `preEtaRows` + `visibleRows` useMemo pair from
 * fe/index.legacy.html:1502-1614 with type annotations only.
 *
 * Order of operations matches the legacy:
 *   1. featured-axis booleans (AND across active axes)
 *   2. region (OR-union when >1 selected; single region was server-side)
 *   3. terrain (AND across selected types)
 *   4. facilityRaw (AND across selected facilities)
 *   5. collection (AND across selected categories)
 *   6. management level (subset match against mark map)
 *   7. ETA layer — hide rows whose batch result isn't `within`
 *   8. user-location distance sort (closest-first; nulls fall to bottom)
 */
export function visibleRows(
  rows: Site[],
  filters: Filters,
  opts: VisibleRowsOpts = {},
): Site[] {
  const {
    featuredAxes = [],
    managementCampLevels = null,
    etaMap = null,
    etaActive = false,
    userLoc = null,
  } = opts;

  let out: Site[] = rows;

  // Featured axes — registry-driven boolean ANDs.
  for (const a of featuredAxes) {
    const key = `has_${a.id}` as const;
    if ((filters as unknown as Record<string, unknown>)[key]) {
      out = out.filter((r) => Boolean(r[key]));
    }
  }

  // Region OR-union when more than one selected (single region was
  // pushed to the server in useSites).
  if (filters.region.size > 1) {
    out = out.filter((r) => typeof r.sido === "string" && filters.region.has(r.sido));
  }

  // Terrain — every selected type must be present on the row.
  if (filters.terrain.size > 0) {
    out = out.filter((r) => {
      const set = new Set(r.location_types ?? []);
      for (const t of filters.terrain) if (!set.has(t)) return false;
      return true;
    });
  }

  // Raw facility tags.
  if (filters.facilityRaw.size > 0) {
    out = out.filter((r) => {
      const fac = new Set(r.facilities ?? []);
      for (const f of filters.facilityRaw) if (!fac.has(f)) return false;
      return true;
    });
  }

  // Collection categories.
  if (filters.collection.size > 0) {
    out = out.filter((r) => {
      const set = new Set(r.categories ?? []);
      for (const c of filters.collection) if (!set.has(c)) return false;
      return true;
    });
  }

  // Management mark filter.
  if (filters.management.size > 0 && managementCampLevels) {
    out = out.filter((r) => {
      const lvl = managementCampLevels.get(r.id);
      return lvl != null && filters.management.has(lvl);
    });
  }

  // ETA overlay.
  if (etaMap && etaActive) {
    out = out.filter((r) => {
      const e = etaMap[r.id];
      return Boolean(e && e.within);
    });
  }

  // Distance attach + sort.
  if (userLoc) {
    const { lat: ulat, lon: ulon } = userLoc;
    const withDist = out.map<Site>((r) => {
      if (r.lat == null || r.lon == null) return { ...r, _distanceKm: null };
      return { ...r, _distanceKm: haversineKm(ulat, ulon, r.lat, r.lon) };
    });
    withDist.sort((a, b) => {
      const ad = a._distanceKm;
      const bd = b._distanceKm;
      if (ad == null && bd == null) return 0;
      if (ad == null) return 1;
      if (bd == null) return -1;
      return ad - bd;
    });
    return withDist;
  }

  return out;
}
