import { useCallback, useEffect, useMemo, useState } from "react";
import { CONCEPT_FILTER_KEYS, type Filters } from "../../shared/filters";
import type { FacetData, FeaturedAxis, MgmtLevel, Site } from "../../shared/types";
import { prettyTag, tagHue } from "./atoms";

/**
 * Server-shape concept facet item — used to bucket /facets.concepts by
 * category. The backend returns more fields per concept; we only need
 * id/name/count/category/is_axis here.
 */
interface ConceptFacet {
  id: string;
  name: string;
  count: number;
  category?: string;
  is_axis?: boolean;
}

// Korean labels for raw r.location_types codes.
// Origin: fe/index.legacy.html:595-605.
const TERRAIN_LABEL: Record<string, string> = {
  valley: "🌊 계곡",
  mountain: "🏔 산",
  forest: "🌲 숲",
  flat: "🟫 평지",
  river: "🏞 강",
  ocean: "🌊 바다",
  lake: "💧 호수",
  island: "🏝 섬",
  etc: "기타",
};

// Korean labels for raw r.facilities codes (camfit english slugs).
// Origin: fe/index.legacy.html:608-632.
const FACILITY_LABEL: Record<string, string> = {
  trampoline: "🤸 트램펄린",
  swimmingPool: "🏊 수영장",
  warmpool: "♨️ 온수풀",
  showerRoom: "🚿 샤워실",
  store: "🛒 매점",
  playground: "🎠 놀이터",
  bbq: "🍖 BBQ",
  canBringPet: "🐕 반려동반",
  pet: "🐾 펫",
  kidsFacility: "👶 키즈시설",
  individualRoom: "🚪 개별룸",
  trail: "🥾 트레일",
  trailer: "🚐 트레일러",
  caravan: "🚚 카라반",
  carCharger: "🔌 EV충전",
  garden: "🌳 정원",
  activity: "🎯 액티비티",
  rent: "🛍 렌탈",
  sled: "🛷 썰매",
  storage: "📦 보관",
  zoo: "🦌 동물원",
  sauna: "🧖 사우나",
  zipline: "🪂 짚라인",
};

// Korean labels for management mark levels.
// Origin: fe/index.legacy.html:635-641.
const MGMT_LEVELS: MgmtLevel[] = ["exceptional", "notable", "recommended", "bib"];
const MGMT_LABEL: Record<MgmtLevel, string> = {
  exceptional: "🏆 최고관리",
  notable: "✨ 우수관리",
  recommended: "👍 추천관리",
  bib: "🎯 양호관리",
};

/**
 * Toggle a chip in a set with modifier-key semantics.
 *   - Plain click: single-replace (or clear if it was the lone selection).
 *   - Ctrl/Cmd/Shift+click: toggle membership (additive AND-mode).
 *
 * Origin: fe/index.legacy.html:646-656.
 */
function toggleChipSelection<T>(
  currentSet: Set<T>,
  value: T,
  ev: React.MouseEvent | { ctrlKey?: boolean; metaKey?: boolean; shiftKey?: boolean } | undefined,
): Set<T> {
  const next = new Set(currentSet);
  const additive = ev && (ev.ctrlKey || ev.metaKey || ev.shiftKey);
  if (additive) {
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  }
  if (next.size === 1 && next.has(value)) return new Set();
  return new Set([value]);
}

/**
 * MultiChip — a chip whose `active` is "in this Set". onPick(value, ev)
 * is called with the raw event so the helper above can read modifier
 * keys.
 *
 * Origin: fe/index.legacy.html:660-677.
 */
function MultiChip({
  value,
  label,
  count,
  active,
  onPick,
  color,
}: {
  value: string;
  label: string;
  count?: number;
  active: boolean;
  onPick: (value: string, ev: React.MouseEvent) => void;
  color?: string;
}) {
  const hue = color || tagHue(value);
  const style: React.CSSProperties = {
    background: `${hue}14`,
    color: hue,
    borderColor: `${hue}33`,
    boxShadow: active ? `inset 0 0 0 1.5px ${hue}` : undefined,
  };
  return (
    <button
      onClick={(e) => onPick(value, e)}
      className="chip"
      style={style}
      title={count != null ? `${count}곳` : ""}
    >
      {active ? "● " : ""}
      {label}
      {count != null ? <span className="opacity-60 ml-1 num">{count}</span> : null}
    </button>
  );
}

/**
 * FilterRow — one heading + N MultiChips. Collapsible header with
 * count badge; renders nothing when items list is empty.
 *
 * Origin: fe/index.legacy.html:679-716.
 */
function FilterRow({
  heading,
  set,
  items,
  onToggle,
  onClear,
  slotKey,
  collapsed,
  onToggleCollapse,
}: {
  heading: string;
  set: Set<string> | undefined;
  items: { value: string; label: string; count?: number }[];
  onToggle: (value: string, ev: React.MouseEvent) => void;
  onClear: () => void;
  slotKey?: string;
  collapsed?: boolean;
  onToggleCollapse?: (key: string) => void;
}) {
  if (!items || items.length === 0) return null;
  const selectedCount = set ? set.size : 0;
  const isCollapsed = !!collapsed;
  // Show count when collapsed (chips hidden) or when 2+ selected.
  const showCount = selectedCount > 0 && (isCollapsed || selectedCount >= 2);
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <button
        type="button"
        onClick={() => onToggleCollapse && slotKey && onToggleCollapse(slotKey)}
        className="text-[10px] uppercase tracking-[0.2em] text-stone-500 mr-1 shrink-0 inline-flex items-center gap-1 hover:text-stone-700"
        title={isCollapsed ? "펼치기" : "접기"}
      >
        <span
          className="opacity-50 num"
          style={{ width: "0.7em", display: "inline-block", textAlign: "center" }}
        >
          {isCollapsed ? "▸" : "▾"}
        </span>
        <span>{heading}</span>
        {showCount ? (
          <span className="ml-1 text-[color:var(--ember)] num">({selectedCount})</span>
        ) : null}
      </button>
      {!isCollapsed && selectedCount > 0 && (
        <button
          onClick={(e) => {
            e.preventDefault();
            onClear();
          }}
          className="chip"
          style={{
            background: "rgba(26,26,23,0.04)",
            color: "rgba(26,26,23,0.55)",
            borderColor: "rgba(26,26,23,0.18)",
          }}
          title="이 차원 선택 해제"
        >
          ×
        </button>
      )}
      {!isCollapsed &&
        items.map((it) => (
          <MultiChip
            key={it.value}
            value={it.value}
            label={it.label}
            count={it.count}
            active={set ? set.has(it.value) : false}
            onPick={onToggle}
          />
        ))}
    </div>
  );
}

export interface FilterBarProps {
  filters: Filters;
  setFilters: React.Dispatch<React.SetStateAction<Filters>>;
  clearAll: () => void;
  facets: FacetData;
  rows: Site[];
  mgmtLevelCounts: Record<MgmtLevel, number>;
  featuredAxes: FeaturedAxis[];
}

export function FilterBar({
  filters,
  setFilters,
  clearAll,
  facets,
  rows,
  mgmtLevelCounts,
  featuredAxes,
}: FilterBarProps) {
  // Sido list from /facets.regions (de-duplicated).
  const sidoSet = useMemo(
    () => Array.from(new Set((facets.regions || []).map((r) => r.sido).filter(Boolean))).sort(),
    [facets],
  );

  // Bucket /facets.concepts by category.
  const conceptsByCat = useMemo(() => {
    const buckets: Record<string, { value: string; label: string; count: number }[]> = {};
    for (const c of (facets.concepts || []) as ConceptFacet[]) {
      if (!c || (c.count || 0) <= 0) continue;
      const cat = c.category || "_other";
      if (!buckets[cat]) buckets[cat] = [];
      buckets[cat].push({ value: c.id, label: c.name, count: c.count });
    }
    for (const k of Object.keys(buckets)) {
      const arr = buckets[k]!;
      arr.sort((a, b) => (b.count || 0) - (a.count || 0));
      buckets[k] = arr.slice(0, 40);
    }
    return buckets;
  }, [facets]);

  // Concept axes (is_axis=true). Drop ones already covered by the 대표축 row.
  const conceptAxes = useMemo(
    () =>
      (facets.concept_axes as ConceptFacet[] | undefined || [])
        .filter((c) => (c.count || 0) > 0)
        .filter((c) => c.id !== "valley" && c.id !== "kids")
        .map((c) => ({ value: c.id, label: c.name, count: c.count })),
    [facets],
  );

  // Terrain — aggregate r.location_types over rows.
  const terrainItems = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows || []) {
      for (const t of (r.location_types || []) as string[])
        counts.set(t, (counts.get(t) || 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([code, count]) => ({ value: code, label: TERRAIN_LABEL[code] || code, count }));
  }, [rows]);

  // Facility (raw English codes) — aggregate over rows.
  const facilityRawItems = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows || []) {
      for (const f of (r.facilities || []) as string[])
        counts.set(f, (counts.get(f) || 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 30)
      .map(([code, count]) => ({ value: code, label: FACILITY_LABEL[code] || code, count }));
  }, [rows]);

  // Collections — `콜렉션:*` / `테마:*` in r.categories.
  const collectionItems = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rows || []) {
      for (const c of (r.categories || []) as string[]) {
        if (typeof c !== "string") continue;
        if (c.startsWith("콜렉션:") || c.startsWith("테마:")) {
          counts.set(c, (counts.get(c) || 0) + 1);
        }
      }
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([name, count]) => ({ value: name, label: prettyTag(name), count }));
  }, [rows]);

  // Management — fixed 4 levels, counts from useMemo over the global mark map.
  const managementItems = useMemo(
    () =>
      MGMT_LEVELS.filter((lv) => (mgmtLevelCounts?.[lv] || 0) > 0).map((lv) => ({
        value: lv,
        label: MGMT_LABEL[lv] || lv,
        count: mgmtLevelCounts?.[lv] || 0,
      })),
    [mgmtLevelCounts],
  );

  // Toggle helper bound to a particular filter slot.
  const makeToggle =
    <K extends keyof Filters>(key: K) =>
    (value: string, ev: React.MouseEvent) =>
      setFilters((prev) => ({
        ...prev,
        [key]: toggleChipSelection(prev[key] as Set<string>, value, ev),
      }));
  const makeClear = (key: keyof Filters) => () =>
    setFilters((prev) => ({ ...prev, [key]: new Set() } as Filters));

  // Collapse state — keys are slotKeys + section markers. Persisted to localStorage.
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem("cf:filterCollapse");
      if (raw) return new Set(JSON.parse(raw) as string[]);
    } catch {
      /* ignore parse/storage errors */
    }
    return new Set(["__section:semantic", "__section:direct"]);
  });
  useEffect(() => {
    try {
      localStorage.setItem("cf:filterCollapse", JSON.stringify([...collapsed]));
    } catch {
      /* quota / private mode — non-fatal */
    }
  }, [collapsed]);
  const toggleCollapsed = useCallback((key: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const semanticCollapsed = collapsed.has("__section:semantic");
  const directCollapsed = collapsed.has("__section:direct");
  const semanticActiveCount = CONCEPT_FILTER_KEYS.reduce(
    (n, k) => n + ((filters[k] as Set<string> | undefined)?.size || 0),
    0,
  );
  const directActiveCount =
    (filters.terrain.size || 0) +
    (filters.facilityRaw.size || 0) +
    (filters.collection.size || 0) +
    (filters.management.size || 0);

  // Sido row uses the multi-select helper too.
  const regionItems = useMemo(
    () => sidoSet.map((s) => ({ value: s, label: s })),
    [sidoSet],
  );

  // Count active dimensions for the "전체 해제" button visibility.
  const anyFeaturedAxisActive = (featuredAxes || []).some((a) => filters[`has_${a.id}`]);
  const anyActive =
    anyFeaturedAxisActive ||
    filters.region.size > 0 ||
    CONCEPT_FILTER_KEYS.some((k) => ((filters[k] as Set<string> | undefined)?.size || 0) > 0) ||
    filters.terrain.size > 0 ||
    filters.collection.size > 0 ||
    filters.facilityRaw.size > 0 ||
    filters.management.size > 0;

  return (
    <div className="space-y-3">
      {/* Modifier-key hint + clear-all */}
      <div className="flex items-center gap-2 text-[11px] text-stone-500">
        <span>
          <span className="kbd">Ctrl</span>/<span className="kbd">⌘</span> 클릭 = 다중 선택 (AND) ·
          다시 클릭 = 해제
        </span>
        {anyActive && (
          <button
            onClick={clearAll}
            className="btn ml-auto"
            style={{ padding: "3px 10px", fontSize: "11px" }}
          >
            전체 해제
          </button>
        )}
      </div>

      {/* Featured boolean axes — registry-driven single-toggle shortcuts. */}
      {featuredAxes.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] uppercase tracking-[0.2em] text-stone-500 mr-1">
            대표축
          </span>
          {featuredAxes.map((a) => {
            const k = `has_${a.id}` as const;
            const active = !!filters[k];
            const toneClass = a.tone === "warm" ? "warm" : a.tone === "bark" ? "bark" : "";
            return (
              <button
                key={a.id}
                onClick={() =>
                  setFilters((prev) => ({ ...prev, [k]: !prev[k] } as Filters))
                }
                className={`chip ${toneClass} ${active ? "" : "opacity-70 hover:opacity-100"}`}
                style={
                  active ? { boxShadow: "inset 0 0 0 1.5px var(--moss-deep)" } : undefined
                }
              >
                {active ? "● " : ""}
                {a.icon} {a.ko}
              </button>
            );
          })}
        </div>
      )}

      {/* Region — multi-select sido */}
      <div data-region-row>
        <FilterRow
          heading="지역"
          slotKey="region"
          collapsed={collapsed.has("region")}
          onToggleCollapse={toggleCollapsed}
          set={filters.region}
          items={regionItems}
          onToggle={makeToggle("region")}
          onClear={makeClear("region")}
        />
      </div>

      {/* ── 시멘틱 필터 ── */}
      <button
        type="button"
        onClick={() => toggleCollapsed("__section:semantic")}
        className="w-full text-left text-[10px] uppercase tracking-[0.2em] text-stone-400 pt-1 border-t hairline inline-flex items-center gap-1.5 hover:text-stone-600"
      >
        <span
          className="opacity-50 num"
          style={{ width: "0.7em", display: "inline-block", textAlign: "center" }}
        >
          {semanticCollapsed ? "▸" : "▾"}
        </span>
        <span>시멘틱 필터</span>
        {semanticActiveCount > 0 ? (
          <span className="ml-1 text-[color:var(--ember)] num">({semanticActiveCount})</span>
        ) : null}
      </button>

      {!semanticCollapsed && (
        <>
          <FilterRow
            heading="컨셉 축"
            slotKey="conceptAxis"
            collapsed={collapsed.has("conceptAxis")}
            onToggleCollapse={toggleCollapsed}
            set={filters.conceptAxis}
            items={conceptAxes}
            onToggle={makeToggle("conceptAxis")}
            onClear={makeClear("conceptAxis")}
          />
          <FilterRow
            heading="자연뷰"
            slotKey="view"
            collapsed={collapsed.has("view")}
            onToggleCollapse={toggleCollapsed}
            set={filters.view}
            items={conceptsByCat.view || []}
            onToggle={makeToggle("view")}
            onClear={makeClear("view")}
          />
          <FilterRow
            heading="시설"
            slotKey="facility"
            collapsed={collapsed.has("facility")}
            onToggleCollapse={toggleCollapsed}
            set={filters.facility}
            items={conceptsByCat.facility || []}
            onToggle={makeToggle("facility")}
            onClear={makeClear("facility")}
          />
          <FilterRow
            heading="키즈시설"
            slotKey="kidsFacility"
            collapsed={collapsed.has("kidsFacility")}
            onToggleCollapse={toggleCollapsed}
            set={filters.kidsFacility}
            items={conceptsByCat.kids_facility || []}
            onToggle={makeToggle("kidsFacility")}
            onClear={makeClear("kidsFacility")}
          />
          <FilterRow
            heading="사이트 재질"
            slotKey="surface"
            collapsed={collapsed.has("surface")}
            onToggleCollapse={toggleCollapsed}
            set={filters.surface}
            items={conceptsByCat.surface || []}
            onToggle={makeToggle("surface")}
            onClear={makeClear("surface")}
          />
          <FilterRow
            heading="사이트 공간"
            slotKey="space"
            collapsed={collapsed.has("space")}
            onToggleCollapse={toggleCollapsed}
            set={filters.space}
            items={conceptsByCat.space || []}
            onToggle={makeToggle("space")}
            onClear={makeClear("space")}
          />
          <FilterRow
            heading="주차"
            slotKey="parking"
            collapsed={collapsed.has("parking")}
            onToggleCollapse={toggleCollapsed}
            set={filters.parking}
            items={conceptsByCat.parking || []}
            onToggle={makeToggle("parking")}
            onClear={makeClear("parking")}
          />
          <FilterRow
            heading="대상"
            slotKey="audience"
            collapsed={collapsed.has("audience")}
            onToggleCollapse={toggleCollapsed}
            set={filters.audience}
            items={conceptsByCat.audience || []}
            onToggle={makeToggle("audience")}
            onClear={makeClear("audience")}
          />
          <FilterRow
            heading="분위기"
            slotKey="vibe"
            collapsed={collapsed.has("vibe")}
            onToggleCollapse={toggleCollapsed}
            set={filters.vibe}
            items={conceptsByCat.vibe || []}
            onToggle={makeToggle("vibe")}
            onClear={makeClear("vibe")}
          />
        </>
      )}

      {/* ── 직접 필터 ── */}
      <button
        type="button"
        onClick={() => toggleCollapsed("__section:direct")}
        className="w-full text-left text-[10px] uppercase tracking-[0.2em] text-stone-400 pt-1 border-t hairline inline-flex items-center gap-1.5 hover:text-stone-600"
      >
        <span
          className="opacity-50 num"
          style={{ width: "0.7em", display: "inline-block", textAlign: "center" }}
        >
          {directCollapsed ? "▸" : "▾"}
        </span>
        <span>직접 필터</span>
        {directActiveCount > 0 ? (
          <span className="ml-1 text-[color:var(--ember)] num">({directActiveCount})</span>
        ) : null}
      </button>

      {!directCollapsed && (
        <>
          <FilterRow
            heading="지형"
            slotKey="terrain"
            collapsed={collapsed.has("terrain")}
            onToggleCollapse={toggleCollapsed}
            set={filters.terrain}
            items={terrainItems}
            onToggle={makeToggle("terrain")}
            onClear={makeClear("terrain")}
          />
          <FilterRow
            heading="시설(원본)"
            slotKey="facilityRaw"
            collapsed={collapsed.has("facilityRaw")}
            onToggleCollapse={toggleCollapsed}
            set={filters.facilityRaw}
            items={facilityRawItems}
            onToggle={makeToggle("facilityRaw")}
            onClear={makeClear("facilityRaw")}
          />
          <FilterRow
            heading="컬렉션"
            slotKey="collection"
            collapsed={collapsed.has("collection")}
            onToggleCollapse={toggleCollapsed}
            set={filters.collection}
            items={collectionItems}
            onToggle={makeToggle("collection")}
            onClear={makeClear("collection")}
          />
          <FilterRow
            heading="관리수준"
            slotKey="management"
            collapsed={collapsed.has("management")}
            onToggleCollapse={toggleCollapsed}
            set={filters.management as Set<string>}
            items={managementItems}
            onToggle={makeToggle("management")}
            onClear={makeClear("management")}
          />
        </>
      )}
    </div>
  );
}
