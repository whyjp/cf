/**
 * Domain types — fe-friendly projection (BFF post-processing shape).
 *
 * Source of truth: fe/index.legacy.html App() row consumers (`r.lat`,
 * `r.lon`, `r.sido`, `r.collections`, `r.location_types`, `r.facilities`,
 * `r.has_<axis>`, `r.categories`, etc.) + backend
 * cf_be_api.domain.featured_axes.
 *
 * `Site` is intentionally permissive (`[extra: string]: unknown`) for now
 * because rows carry many camp columns plus dynamic `has_<axis>` boolean
 * flags injected per-request by the featured-axis registry. Known fields
 * are typed; the rest is unknown to nudge call sites toward narrowing
 * before consuming.
 */

export interface Site {
  id: string;
  name?: string;
  sido?: string;
  sigungu?: string;
  lat?: number | null;
  lon?: number | null;

  /** Human-readable location categories (e.g. "감성캠핑", "글램핑") */
  categories?: string[];
  /** Terrain (e.g. "valley", "forest", "lakeside") — server-derived */
  location_types?: string[];
  /** Raw facility tags from upstream feed */
  facilities?: string[];
  /** Curated collection name set */
  collections?: { name: string }[];

  address?: string;
  region_sigungu?: string;

  /** Per-row distance from user location, attached client-side after sort. */
  _distanceKm?: number | null;

  /** Dynamic `has_<axis>` boolean flags + any other backend column. */
  [extra: string]: unknown;
}

/**
 * Photo embedded in a `SiteDetail` payload — backend BFF post-processing
 * shape. Mirrors the projection emitted by `cf_be_for_fe` for /sites/:id.
 */
export interface SiteDetailPhoto {
  url: string;
  thumb: string;
}

/**
 * Single review row preview returned by /sites/:id under `reviews_top`.
 * Backend trims to ~6 entries; the full set lives behind a separate
 * /reviews endpoint (not yet wired into FE).
 */
export interface SiteDetailReview {
  user?: string;
  season?: string;
  userType?: string;
  numOfDays?: number;
  score?: number | null;
  text: string;
}

/**
 * /sites/:id response — extends the list-row `Site` with detail-only fields
 * (description, brief, contact, photos, reviews, etc.) emitted by
 * `cf_be_for_fe` only on the detail endpoint. All fields are optional —
 * server may omit them when upstream camfit data is sparse.
 *
 * Consumed by `useDetail` → DetailPanel (desktop) / DetailSheet (mobile).
 */
export interface SiteDetail extends Site {
  region_sido?: string;
  url?: string;
  description?: string;
  brief?: string;
  locationBrief?: string;
  contact?: string;
  priceStartFrom?: number;
  priceEndTo?: number;
  numOfReviews?: number;
  bookmarkCount?: number;
  photos?: SiteDetailPhoto[];
  reviews_top?: SiteDetailReview[];
  reviews_total?: number;
  hashtags?: string[];
}

/**
 * 대표축 metadata. Backend-driven via GET /featured-axes — see
 * `useFeaturedAxes`. Field shape mirrors
 * cf_be_api.domain.featured_axes.FeaturedAxis. `name` is an alias-friendly
 * synonym kept for forward-compat with newer BFF projections.
 */
export interface FeaturedAxis {
  /** snake_case id; row carries `has_<id>` boolean. */
  id: string;
  /** Korean display label. */
  ko: string;
  /** Emoji. */
  icon?: string;
  /** Chip color family — "" | "warm" | "bark". */
  tone?: "" | "warm" | "bark";
  /** Optional alias of ko for plan-spec callers. */
  name?: string;
  /** Optional axis color (hex) — overrides AXIS_COLORS when present. */
  color?: string;
  /** Concept ids implied by this axis (server projection forward-compat). */
  conceptIds?: string[];
  /** Server-side keyword matchers (rarely needed on client). */
  keywords?: string[];
}

export interface FacetData {
  regions: Array<{ sido: string; sigungu: string; count: number }>;
  concept_axes: unknown[];
  concepts: unknown[];
  themes: unknown[];
}

export type MgmtLevel = "bib" | "recommended" | "notable" | "exceptional";

export interface MgmtMark {
  camp_id: string;
  level: MgmtLevel;
}

export interface EtaResult {
  /** Driving minutes from origin to camp. */
  minutes?: number;
  /** Whether `minutes` is within the user-requested cap. */
  within?: boolean;
  /** Echoed result error (e.g. routing failure for this id). */
  error?: string;
  /** Backend echoes the camp id alongside the result. */
  id?: string;
  /** Routing source label ("etago", "cache", ...). */
  source?: string;
}

/**
 * /eta/batch response body.
 *
 * Backend currently returns `{ results: EtaResult[], within_count, checked }`.
 * The client also keeps a `Record<id, EtaResult>` for fast lookup —
 * `useEtaBatch` indexes the array into that record.
 */
export interface EtaBatchResponse {
  results: EtaResult[] | Record<string, EtaResult>;
  within_count?: number;
  checked?: number;
}

export interface UserCoords {
  lat: number;
  lon: number;
}

export type UserLocStatus =
  | "idle"
  | "asking"
  | "ok"
  | "denied"
  | "error"
  | "unsupported";
