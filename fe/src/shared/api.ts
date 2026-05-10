/**
 * API base URL — chooses between same-origin (BFF mount or Vite dev with
 * proxy) and an explicit override (admin host, e2e fixtures).
 *
 * - Vite dev (port 5173): proxy in vite.config.ts forwards /sites etc. to
 *   the local BFF on 8070, so base = "" works (relative requests stay on
 *   :5173 and the proxy rewrites).
 * - Production (BFF serves fe/dist): same origin → base = "".
 * - Override via VITE_API_BASE (e.g. "http://admin.example.com:8071") for
 *   split-host deployments and Playwright fixtures.
 */
export const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "";

export async function getJson<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
): Promise<T> {
  const url = new URL(API_BASE + path, location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  const r = await fetch(url.toString());
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

export async function postJson<T, B>(
  path: string,
  body: B,
  signal?: AbortSignal,
): Promise<T> {
  const r = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json() as Promise<T>;
}

/**
 * Build a /sites URL with the same param shape useSites uses internally.
 *
 * - region: single sido (server-side). When >1 region selected, callers
 *   should drop region here and filter client-side.
 * - concept: repeated `concept=<id>` params (server-side AND).
 */
export function buildSitesUrl(params: {
  region?: string;
  concept?: string[];
}): string {
  const u = new URLSearchParams();
  if (params.region) u.append("region", params.region);
  for (const id of params.concept ?? []) u.append("concept", id);
  return `${API_BASE}/sites?${u.toString()}`;
}
