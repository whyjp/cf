import { useCallback, useRef, useState } from "react";
import { API_BASE, postJson } from "../api";
import type { EtaBatchResponse, EtaResult, UserCoords } from "../types";

interface BatchInput {
  /** Origin can be free-text address (geocoded by BE) or {lat,lon}. */
  origin: UserCoords | string;
  ids: string[];
  max_minutes?: number | null;
}

interface EtaSummary {
  within_count?: number;
  checked?: number;
}

/**
 * /eta/batch wrapper bundling loading/results/error/abort + a one-shot
 * cache delete on `clear`.
 *
 * `apply` cancels any in-flight request and replaces results. Errors
 * other than AbortError surface via `err`. The legacy hook also
 * invoked `alert` and `confirm` directly (legacy:1547-1554, 1573); we
 * keep this hook UI-agnostic — callers decide how to surface the
 * `ETA_HARD_CAP` warning and apply errors.
 *
 * Origin: fetchEtaBatch (legacy:299-308) + ETA state from App
 * (legacy:1481-1489, 1539-1583).
 */
export function useEtaBatch(): {
  results: Record<string, EtaResult> | null;
  summary: EtaSummary | null;
  loading: boolean;
  err: string | null;
  apply: (input: BatchInput) => Promise<void>;
  clear: () => void;
} {
  const [results, setResults] = useState<Record<string, EtaResult> | null>(
    null,
  );
  const [summary, setSummary] = useState<EtaSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const apply = useCallback(async (input: BatchInput) => {
    if (abortRef.current) abortRef.current.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLoading(true);
    setErr(null);
    try {
      const body = {
        origin: input.origin,
        ids: input.ids,
        max_minutes: input.max_minutes ?? null,
        concurrency: 4,
        timeout_s: 12,
      };
      const data = await postJson<EtaBatchResponse, typeof body>(
        "/eta/batch",
        body,
        ctrl.signal,
      );
      // Backend returns `results: EtaResult[]` (legacy:1567-1568) — index
      // into a record for fast id lookup. Tolerate the alternative
      // record shape too in case a future projection switches.
      const m: Record<string, EtaResult> = {};
      if (Array.isArray(data.results)) {
        for (const it of data.results) {
          if (it && typeof it.id === "string") m[it.id] = it;
        }
      } else if (data.results && typeof data.results === "object") {
        Object.assign(m, data.results);
      }
      setResults(m);
      setSummary({ within_count: data.within_count, checked: data.checked });
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setErr(String(e));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const clear = useCallback(() => {
    setResults(null);
    setSummary(null);
    setErr(null);
    // Mirrors legacy:1582 — best-effort cache wipe; failures swallowed.
    fetch(`${API_BASE}/eta/cache`, { method: "DELETE" }).catch(() => {});
  }, []);

  return { results, summary, loading, err, apply, clear };
}
