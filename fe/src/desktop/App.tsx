import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ETA_HARD_CAP } from "../shared/constants";
import type { Filters } from "../shared/filters";
import { haversineKm } from "../shared/geo";
import { useDetail as _useDetailUnused } from "../shared/hooks/useDetail";
import { useEtaBatch } from "../shared/hooks/useEtaBatch";
import { useFacets } from "../shared/hooks/useFacets";
import { useFeaturedAxes } from "../shared/hooks/useFeaturedAxes";
import { useManagementMarks } from "../shared/hooks/useManagementMarks";
import { useSites } from "../shared/hooks/useSites";
import { useUserLocation } from "../shared/hooks/useUserLocation";
import type { MgmtLevel, Site } from "../shared/types";
import { Stat } from "./components/atoms";
import { CampList } from "./components/CampList";
import { DetailPanel } from "./components/DetailPanel";
import { EtaBar, minutesFrom } from "./components/EtaBar";
import { FilterBar } from "./components/FilterBar";
import { LocationPill } from "./components/LocationPill";
import { MapView } from "./components/MapView";
import { SearchBox } from "./components/SearchBox";

// `useDetail` is consumed inside DetailPanel; the import above is just to
// keep the original mental model of "App pulls all the data hooks" — but
// TS dislikes unused imports under noUnusedLocals. Touch the binding.
void _useDetailUnused;

/**
 * Root desktop App — state container + layout shell.
 *
 * Origin: fe/index.legacy.html:1426-1784. Behaviour, JSX shape,
 * className strings, event handlers all preserved verbatim. Only the
 * imports shifted to the shared/components packages.
 */
export function App() {
  const [view, setView] = useState<"split" | "map" | "list">("split");
  const featuredAxes = useFeaturedAxes();
  const userLoc = useUserLocation();

  // Multi-select chip state — every long-tail dimension is a Set<string>.
  // The 대표축 row stays as one boolean per axis (`has_<id>`) because the
  // shortcuts are independent toggles, not a multi-pick set.
  const [filters, setFilters] = useState<Filters>(() => ({
    region: new Set<string>(),
    conceptAxis: new Set<string>(),
    view: new Set<string>(),
    facility: new Set<string>(),
    kidsFacility: new Set<string>(),
    surface: new Set<string>(),
    space: new Set<string>(),
    parking: new Set<string>(),
    audience: new Set<string>(),
    vibe: new Set<string>(),
    terrain: new Set<string>(),
    collection: new Set<string>(),
    facilityRaw: new Set<string>(),
    management: new Set<MgmtLevel>(),
  }));
  const clearAll = useCallback(() => {
    setFilters((prev) => {
      const next: Filters = {
        region: new Set(),
        conceptAxis: new Set(),
        view: new Set(),
        facility: new Set(),
        kidsFacility: new Set(),
        surface: new Set(),
        space: new Set(),
        parking: new Set(),
        audience: new Set(),
        vibe: new Set(),
        terrain: new Set(),
        collection: new Set(),
        facilityRaw: new Set(),
        management: new Set(),
      };
      // Preserve `has_<id>: false` keys so axis chips don't blink. Reset
      // any boolean that was true to false; keep any extra keys intact
      // shape-wise.
      for (const k of Object.keys(prev)) {
        if (k.startsWith("has_")) (next as unknown as Record<string, boolean>)[k] = false;
      }
      return next;
    });
  }, []);

  const [pickedId, setPickedId] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<Site[] | null>(null);
  const { data: facets } = useFacets();
  const { rows: sitesRows, loading, err } = useSites(filters);
  const managementCampLevels = useManagementMarks();
  const mgmtLevelCounts = useMemo<Record<MgmtLevel, number>>(() => {
    const m: Record<MgmtLevel, number> = {
      exceptional: 0,
      notable: 0,
      recommended: 0,
      bib: 0,
    };
    if (managementCampLevels)
      for (const lv of managementCampLevels.values()) {
        if (m[lv] != null) m[lv]++;
      }
    return m;
  }, [managementCampLevels]);
  // Effective rows pre-clientside-filtering: search results take priority.
  const rows = useMemo(
    () => (searchResults != null ? searchResults : sitesRows),
    [searchResults, sitesRows],
  );

  // ETA state — useEtaBatch wraps fetch+abort; App layers in candidate
  // counting + the hard-cap confirm dialog.
  const [origin, setOrigin] = useState("");
  const [etaHours, setEtaHours] = useState(2);
  const [etaMins, setEtaMins] = useState(0);
  const [etaActive, setEtaActive] = useState(true);
  const eta = useEtaBatch();
  const etaMap = eta.results;

  // List of camps that ETA SHOULD run against — every active filter
  // applied EXCEPT the ETA layer itself. Defined before applyEta and
  // visibleRows so both can read it; the candidate set is what the user
  // already narrowed via region/concept/has_*/terrain/collection chips.
  const preEtaRows = useMemo(() => {
    let out: Site[] = rows;
    for (const a of featuredAxes) {
      if (filters[`has_${a.id}`]) out = out.filter((r) => r[`has_${a.id}`]);
    }
    if (filters.region.size > 1)
      out = out.filter((r) => typeof r.sido === "string" && filters.region.has(r.sido));
    if (filters.terrain.size > 0) {
      out = out.filter((r) => {
        const set = new Set((r.location_types || []) as string[]);
        for (const t of filters.terrain) if (!set.has(t)) return false;
        return true;
      });
    }
    if (filters.facilityRaw.size > 0) {
      out = out.filter((r) => {
        const fac = new Set((r.facilities || []) as string[]);
        for (const f of filters.facilityRaw) if (!fac.has(f)) return false;
        return true;
      });
    }
    if (filters.collection.size > 0) {
      out = out.filter((r) => {
        const set = new Set((r.categories || []) as string[]);
        for (const c of filters.collection) if (!set.has(c)) return false;
        return true;
      });
    }
    if (filters.management.size > 0 && managementCampLevels) {
      out = out.filter((r) => {
        const lvl = managementCampLevels.get(r.id);
        return lvl != null && filters.management.has(lvl);
      });
    }
    return out;
  }, [rows, filters, managementCampLevels, featuredAxes]);

  const applyEta = useCallback(async () => {
    if (!origin.trim() || preEtaRows.length === 0) return;
    const candidates = preEtaRows.filter((r) => r.lat != null && r.lon != null);
    if (candidates.length > ETA_HARD_CAP) {
      const proceed = confirm(
        `${candidates.length}개 캠프에 ETA 계산을 시도합니다 (캠프당 ~1–3초). ` +
          `시간이 오래 걸릴 수 있습니다. 먼저 지역/컨셉 필터로 ${ETA_HARD_CAP}개 이하로 줄이시면 빠릅니다.\n\n` +
          `그래도 진행하시겠습니까?`,
      );
      if (!proceed) return;
    }
    const max = minutesFrom(etaHours, etaMins) || null;
    try {
      await eta.apply({
        origin: origin.trim(),
        ids: candidates.map((r) => r.id),
        max_minutes: max,
      });
    } catch (e) {
      // useEtaBatch surfaces non-Abort errors via its `err`. Mirror legacy
      // alert() so users notice failures even if the small `err` chip is
      // missed in the header crowd.
      const msg = e instanceof Error ? e.message : String(e);
      if (msg && !msg.includes("AbortError")) alert(`ETA 적용 실패: ${msg}`);
    }
  }, [origin, etaHours, etaMins, preEtaRows, eta]);

  const clearEta = useCallback(() => {
    eta.clear();
  }, [eta]);

  // visibleRows = preEtaRows + ETA layer (when applied & active) + sort by
  // straight-line distance from the user's current location (when known).
  const visibleRows = useMemo(() => {
    let out: Site[] = preEtaRows;
    if (etaMap && etaActive) {
      out = out.filter((r) => {
        const e = etaMap[r.id];
        return Boolean(e && e.within);
      });
    }
    if (userLoc.coords) {
      const { lat: ulat, lon: ulon } = userLoc.coords;
      const withDist = out.map<Site>((r) => {
        if (r.lat == null || r.lon == null) return { ...r, _distanceKm: null };
        return { ...r, _distanceKm: haversineKm(ulat, ulon, r.lat, r.lon) };
      });
      withDist.sort((a, b) => {
        if (a._distanceKm == null && b._distanceKm == null) return 0;
        if (a._distanceKm == null) return 1;
        if (b._distanceKm == null) return -1;
        return a._distanceKm - b._distanceKm;
      });
      return withDist;
    }
    return out;
  }, [preEtaRows, etaMap, etaActive, userLoc.coords]);

  const focused = useMemo(
    () => visibleRows.find((r) => r.id === pickedId) || null,
    [visibleRows, pickedId],
  );

  const total = visibleRows.length;
  const withCoord = visibleRows.filter((r) => r.lat != null && r.lon != null).length;
  const featuredCounts = useMemo(
    () =>
      featuredAxes.map((a) => ({
        ko: a.ko,
        icon: a.icon,
        n: visibleRows.filter((r) => r[`has_${a.id}`]).length,
      })),
    [visibleRows, featuredAxes],
  );

  // List pagination + responsive infinite scroll.
  const LIST_PAGE_SIZE = 30;
  const [displayCount, setDisplayCount] = useState(LIST_PAGE_SIZE);
  const listScrollRef = useRef<HTMLElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    setDisplayCount(LIST_PAGE_SIZE);
    if (listScrollRef.current) listScrollRef.current.scrollTop = 0;
  }, [visibleRows]);
  useEffect(() => {
    const sentinel = sentinelRef.current;
    const root = listScrollRef.current;
    if (!sentinel || !root) return;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setDisplayCount((c) => Math.min(c + LIST_PAGE_SIZE, visibleRows.length));
        }
      },
      { root, rootMargin: "300px 0px" },
    );
    obs.observe(sentinel);
    return () => obs.disconnect();
  }, [visibleRows, view]);
  const displayedRows = useMemo(
    () => visibleRows.slice(0, displayCount),
    [visibleRows, displayCount],
  );

  // Esc key listener — close detail panel. Origin: legacy.html:1786-1791
  // (legacy dispatched a CustomEvent; we just clear the state here since
  // App owns it directly).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPickedId(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <header className="topo border-b hairline flex-shrink-0">
        <div className="max-w-[1500px] mx-auto px-6 py-5 flex items-end justify-between gap-6">
          <div>
            <div className="flex items-center gap-3">
              <svg width="34" height="34" viewBox="0 0 40 40" className="opacity-90">
                <path
                  d="M3 32 L20 6 L37 32 Z"
                  fill="none"
                  stroke="#2c4a3e"
                  strokeWidth="2"
                  strokeLinejoin="round"
                />
                <path d="M11 32 L20 18 L29 32 Z" fill="#2c4a3e" />
                <circle cx="32" cy="11" r="2.5" fill="#c8553d" />
              </svg>
              <div>
                <div className="text-[10px] uppercase tracking-[0.3em] text-stone-500 font-medium">
                  camfit-puller
                </div>
                <h1 className="display text-2xl font-bold leading-none mt-0.5">
                  한국 캠핑장 지도
                </h1>
              </div>
            </div>
          </div>
          <div className="hidden md:flex gap-6 items-end">
            <Stat label="총" value={total.toLocaleString()} sub="필터 적용 후" />
            <Stat
              label="좌표"
              value={`${withCoord}`}
              sub={total ? `${Math.round((withCoord / total) * 100)}%` : "—"}
            />
            {featuredCounts.length > 0 && (
              <Stat
                label={featuredCounts.map((c) => c.icon).join(" ")}
                value={featuredCounts.map((c) => c.n).join(" / ")}
              />
            )}
            <LocationPill userLoc={userLoc} />
            <SearchBox
              axes={featuredAxes}
              onPickResult={(arr) => {
                setSearchResults(arr);
                if (arr && arr.length > 0 && arr[0]?.id != null) setPickedId(arr[0].id);
              }}
            />
            <div className="toggle-pill">
              <button
                className={view === "split" ? "active" : ""}
                onClick={() => setView("split")}
              >
                분할
              </button>
              <button
                className={view === "map" ? "active" : ""}
                onClick={() => setView("map")}
              >
                지도
              </button>
              <button
                className={view === "list" ? "active" : ""}
                onClick={() => setView("list")}
              >
                리스트
              </button>
            </div>
            <a href="/graph.html" className="btn">
              그래프 →
            </a>
          </div>
        </div>
        <div className="max-w-[1500px] mx-auto px-6 pb-4 space-y-3">
          {searchResults != null && (
            <div
              className="flex items-center gap-2 text-[12px] px-3 py-2 rounded-lg border hairline"
              style={{
                background: "rgba(200,85,61,0.08)",
                color: "var(--ember)",
                borderColor: "rgba(200,85,61,0.25)",
              }}
            >
              <span>
                🔎 검색결과 <span className="num font-semibold">{searchResults.length}</span>건
                표시 중
              </span>
              <button onClick={() => setSearchResults(null)} className="btn ml-auto">
                전체보기
              </button>
            </div>
          )}
          <FilterBar
            filters={filters}
            setFilters={setFilters}
            clearAll={clearAll}
            facets={facets}
            rows={rows}
            mgmtLevelCounts={mgmtLevelCounts}
            featuredAxes={featuredAxes}
          />
          <EtaBar
            origin={origin}
            setOrigin={setOrigin}
            hours={etaHours}
            setHours={setEtaHours}
            mins={etaMins}
            setMins={setEtaMins}
            etaActive={etaActive}
            setEtaActive={setEtaActive}
            onApply={applyEta}
            onClear={clearEta}
            loading={eta.loading}
            summary={eta.summary}
            candidateCount={preEtaRows.filter((r) => r.lat != null && r.lon != null).length}
            hardCap={ETA_HARD_CAP}
          />
        </div>
      </header>

      {/* Main */}
      <main
        className="flex-1 min-h-0 max-w-[1500px] w-full mx-auto px-6 py-5 grid gap-5 overflow-hidden"
        style={{
          gridTemplateColumns: view === "split" ? "minmax(340px, 420px) 1fr" : "1fr",
        }}
      >
        {(view === "split" || view === "list") && (
          <section
            ref={listScrollRef as React.RefObject<HTMLElement>}
            className="min-h-0 h-full overflow-y-auto pr-1"
          >
            {loading && <div className="text-xs text-stone-500 mb-2">불러오는 중…</div>}
            {err && (
              <div className="text-xs text-[color:var(--ember)] mb-2">API 연결 실패: {err}</div>
            )}
            <CampList
              rows={displayedRows}
              onPick={setPickedId}
              selectedId={pickedId}
              etaMap={etaMap}
              axes={featuredAxes}
            />
            {visibleRows.length > 0 && displayCount < visibleRows.length && (
              <div ref={sentinelRef} className="text-center text-[11px] text-stone-500 py-4">
                더 불러오는 중…{" "}
                <span className="num">
                  {displayCount} / {visibleRows.length.toLocaleString()}
                </span>
              </div>
            )}
            {visibleRows.length > 0 && displayCount >= visibleRows.length && (
              <div className="text-center text-[11px] text-stone-400 py-3">
                — 끝 (<span className="num">{visibleRows.length.toLocaleString()}</span>곳) —
              </div>
            )}
          </section>
        )}
        {(view === "split" || view === "map") && (
          <section className="card overflow-hidden h-full min-h-0">
            <MapView
              rows={visibleRows}
              onPick={setPickedId}
              focused={focused}
              etaMap={etaMap}
              axes={featuredAxes}
              userLoc={userLoc}
            />
          </section>
        )}
      </main>

      <footer className="border-t hairline text-[11px] text-stone-500 px-6 py-3 flex items-center justify-between flex-shrink-0">
        <span>지도 © OpenStreetMap contributors · 데이터: camfit-puller crawl</span>
        <span className="num">
          단축키: <span className="kbd">esc</span> 패널 닫기
        </span>
      </footer>

      <DetailPanel
        id={pickedId}
        onClose={() => setPickedId(null)}
        eta={pickedId && etaMap ? etaMap[pickedId] : null}
        axes={featuredAxes}
      />
    </div>
  );
}
