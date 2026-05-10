import { useEffect, useMemo, useState } from "react";
import { API_BASE } from "../api";
import { CONCEPT_FILTER_KEYS, setSerialize, type Filters } from "../filters";
import type { Site } from "../types";

/**
 * GET /sites with server-side params (region single sido + concept[]).
 *
 * Server-side:
 *   - `region`: only when EXACTLY one sido is selected; multi-region
 *     selection falls back to client-side OR-union in `visibleRows`.
 *   - `concept[]`: union across CONCEPT_FILTER_KEYS, repeated as
 *     `concept=<id>` (server AND semantics, by concept ID).
 *
 * Client-side filters (terrain/collection/facilityRaw/management) live
 * in `visibleRows` because they read columns the server doesn't index.
 *
 * Origin: fe/index.legacy.html:161-201.
 */
export function useSites(filters: Filters): {
  rows: Site[];
  loading: boolean;
  err: string | null;
} {
  const [rows, setRows] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Re-key when any concept slot changes. Set identity flips every
  // render, so we serialize each slot to a stable string for the deps.
  const conceptKey = useMemo(
    () =>
      CONCEPT_FILTER_KEYS.map((k) => setSerialize(filters[k])).join("/"),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    CONCEPT_FILTER_KEYS.map((k) => filters[k]),
  );
  const regionKey = useMemo(() => setSerialize(filters.region), [filters.region]);

  useEffect(() => {
    const params = new URLSearchParams();
    // Region: only push to server when exactly one is picked. With 0 we
    // want the unfiltered result; with >1 we filter client-side to the
    // OR-union in `visibleRows`.
    if (filters.region.size === 1) {
      const [only] = filters.region;
      if (only) params.append("region", only);
    }
    // Concept-shape sets unioned → repeated concept= params.
    const conceptIds = new Set<string>();
    for (const k of CONCEPT_FILTER_KEYS) {
      const s = filters[k];
      if (!s) continue;
      for (const v of s) conceptIds.add(v);
    }
    for (const id of conceptIds) params.append("concept", id);

    setLoading(true);
    setErr(null);
    fetch(`${API_BASE}/sites?${params.toString()}`)
      .then((r) => r.json())
      .then((d) => setRows(Array.isArray(d) ? d : []))
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regionKey, conceptKey]);
  return { rows, loading, err };
}
