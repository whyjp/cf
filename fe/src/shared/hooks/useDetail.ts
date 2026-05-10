import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { SiteDetail } from "../types";

/**
 * GET /sites/:id — null id resets to null (panel close).
 *
 * Returns `SiteDetail` (Site + detail-only optional fields) so consumers
 * can read description/photos/reviews_top/etc. without `as any` casts.
 *
 * Origin: fe/index.legacy.html:221-228.
 */
export function useDetail(id: string | null): SiteDetail | null {
  const [data, setData] = useState<SiteDetail | null>(null);
  useEffect(() => {
    if (!id) {
      setData(null);
      return;
    }
    getJson<SiteDetail>(`/sites/${id}`)
      .then(setData)
      .catch(() => setData(null));
  }, [id]);
  return data;
}
