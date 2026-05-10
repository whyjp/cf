import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { FacetData } from "../types";

/**
 * GET /facets — once at mount.
 *
 * Shape: { regions:[{sido,sigungu,count}], concept_axes, concepts, themes }.
 * (No `categories`/`facilities` keys — those were stale assumptions in
 * older FE code.)
 *
 * Origin: fe/index.legacy.html:136-145.
 */
export function useFacets(): { data: FacetData; err: string | null } {
  const [data, setData] = useState<FacetData>({
    regions: [],
    concept_axes: [],
    concepts: [],
    themes: [],
  });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    getJson<FacetData>("/facets")
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);
  return { data, err };
}
