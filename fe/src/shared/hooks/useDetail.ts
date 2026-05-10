import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { Site } from "../types";

/**
 * GET /sites/:id — null id resets to null (panel close).
 *
 * Origin: fe/index.legacy.html:221-228.
 */
export function useDetail(id: string | null): Site | null {
  const [data, setData] = useState<Site | null>(null);
  useEffect(() => {
    if (!id) {
      setData(null);
      return;
    }
    getJson<Site>(`/sites/${id}`)
      .then(setData)
      .catch(() => setData(null));
  }, [id]);
  return data;
}
