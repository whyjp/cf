import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { FeaturedAxis } from "../types";

/**
 * GET /featured-axes once at mount → drives the 대표축 chip row, PinDots,
 * CampList per-card chips, FEATURED_NAMES dedup, and visibleRows boolean
 * filter loop. Empty fallback keeps the page functional if the endpoint
 * is unreachable; the 대표축 row simply doesn't render.
 *
 * Origin: fe/index.legacy.html:284-297.
 */
export function useFeaturedAxes(): FeaturedAxis[] {
  const [axes, setAxes] = useState<FeaturedAxis[]>([]);
  useEffect(() => {
    getJson<FeaturedAxis[]>("/featured-axes")
      .then((d) => setAxes(Array.isArray(d) ? d : []))
      .catch(() => setAxes([]));
  }, []);
  return axes;
}
