import { useEffect, useState } from "react";
import { getJson } from "../api";
import type { MgmtLevel, MgmtMark } from "../types";

/**
 * One-shot fetch of all camps that have a management mark, keyed by
 * camp_id. Lets the FE filter by level (bib/recommended/notable/
 * exceptional) without re-querying the server on every chip change.
 *
 * Origin: fe/index.legacy.html:203-219.
 */
export function useManagementMarks(): Map<string, MgmtLevel> | null {
  const [byId, setById] = useState<Map<string, MgmtLevel> | null>(null);
  useEffect(() => {
    getJson<MgmtMark[]>("/marks/management/camps", { limit: 2000 })
      .then((arr) => {
        const m = new Map<string, MgmtLevel>();
        if (Array.isArray(arr)) for (const x of arr) m.set(x.camp_id, x.level);
        setById(m);
      })
      .catch(() => setById(new Map()));
  }, []);
  return byId;
}
