import { useMemo, useState } from "react";
import { TopBar } from "./TopBar";
import { MobileMap } from "./MobileMap";
import { BottomSheet } from "./BottomSheet";
import { MobileCampList } from "./MobileCampList";
import { DetailSheet } from "./DetailSheet";
import { MobileSearchOverlay } from "./MobileSearchOverlay";
import { LocationChip } from "./LocationChip";
import { FilterFAB } from "./FilterFAB";
import { FilterSheet } from "./FilterSheet";
import { EtaSheet } from "./EtaSheet";
import { useSites } from "../../shared/hooks/useSites";
import { ETA_HARD_CAP } from "../../shared/constants";
import type { Filters } from "../../shared/filters";
import type { EtaResult } from "../../shared/types";

/**
 * MobileShell — h-dvh flex column.
 *
 * Layout:
 *   [TopBar 56dp]
 *   [main relative — MobileMap(absolute inset-0)
 *                  + LocationChip(absolute top-3 right-3 z-10)
 *                  + FilterFAB(fixed bottom-32 right-4 z-20)
 *                  + BottomSheet(absolute bottom)]
 *   [DetailSheet         — fixed inset-0 z-50, picked!=null 일 때만]
 *   [MobileSearchOverlay — fixed inset-0 z-50, searchOpen 일 때만]
 *   [FilterSheet         — fixed inset-0 z-50, filterOpen 일 때만]
 *   [EtaSheet            — fixed inset-0 z-50, etaOpen 일 때만]
 *
 * 모달 동시성: 4개 모두 z-50 풀스크린이지만, 각 시트는 자기 토글 button
 * 으로만 열린다. FAB → FilterSheet, BottomSheet header → EtaSheet, 카드 →
 * DetailSheet, TopBar 검색 → SearchOverlay. 사용자가 한 번에 두 시트를
 * 띄울 트리거가 없다 (Plan C3 패턴 그대로 확장).
 *
 * filters state lifted (C2 partial → C4 진짜):
 *   - filters 는 Shell 이 소유. FilterSheet 의 onApply(next) 가 setFilters.
 *   - useSites(filters) 가 server-side region/concept 쿼리 reissue.
 *   - filterCount = filters.region.size — 슬롯 늘어나면 후속 sprint 에서
 *     누적 합으로 확장.
 *
 * etaResults state:
 *   - EtaSheet.onApplied 콜백이 채움. null 이면 "ETA 비활성".
 *   - candidateIds 는 rows.slice(0, ETA_HARD_CAP) — useEtaBatch 가 더 이상
 *     legacy confirm() 경고를 띄우지 않으므로 (review note B2) 절단은 여기서.
 *   - visibleRows = etaResults 가 있으면 within !== false 인 row 만 통과.
 *     visibleRows 가 MobileMap + MobileCampList + 카운터에 모두 흘러간다.
 */
export function MobileShell() {
  const [filters, setFilters] = useState<Filters>(
    { region: new Set() } as Filters,
  );
  const { rows, loading, err } = useSites(filters);
  const [picked, setPicked] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [etaOpen, setEtaOpen] = useState(false);
  const [etaResults, setEtaResults] = useState<Record<string, EtaResult> | null>(
    null,
  );

  const filterCount = filters.region.size;
  // ETA 후보 — lat/lon 있는 row 만, 상한까지 잘라서 EtaSheet 로.
  const candidateIds = useMemo(
    () =>
      rows
        .filter((r) => typeof r.lat === "number" && typeof r.lon === "number")
        .slice(0, ETA_HARD_CAP)
        .map((r) => r.id),
    [rows],
  );
  const totalCandidates = useMemo(
    () =>
      rows.filter(
        (r) => typeof r.lat === "number" && typeof r.lon === "number",
      ).length,
    [rows],
  );

  // ETA layer overlay — within !== false 만 통과 (within=undefined 는 보존).
  const visibleRows = etaResults
    ? rows.filter((r) => etaResults[r.id]?.within !== false)
    : rows;

  return (
    <div className="h-dvh flex flex-col">
      <TopBar onSearch={() => setSearchOpen(true)} />
      <main className="flex-1 relative overflow-hidden">
        <MobileMap rows={visibleRows} onPick={setPicked} />
        <div className="absolute top-3 right-3 z-10">
          <LocationChip />
        </div>
        <FilterFAB count={filterCount} onClick={() => setFilterOpen(true)} />
        <BottomSheet initial="peek">
          <div
            className="px-4 py-3 border-b flex items-center gap-2"
            style={{ borderColor: "var(--border-faint)" }}
          >
            <span className="display font-semibold text-base num">
              {loading ? "…" : visibleRows.length.toLocaleString()}
            </span>
            <span className="text-sm text-stone-500">곳</span>
            {etaResults && (
              <span
                className="ml-1 px-1.5 py-0.5 rounded text-[10px] font-semibold"
                style={{
                  background: "var(--moss)",
                  color: "#f7f4e8",
                }}
              >
                ETA
              </span>
            )}
            <button
              onClick={() => setEtaOpen(true)}
              className="ml-auto text-sm font-medium px-2 py-1 rounded"
              style={{ color: "var(--ember)" }}
              aria-label="ETA 설정"
            >
              ⏱ ETA
            </button>
            {err && (
              <span className="text-xs text-red-600" title={err}>
                error
              </span>
            )}
          </div>
          <MobileCampList rows={visibleRows} onPick={setPicked} />
        </BottomSheet>
      </main>
      <DetailSheet id={picked} onClose={() => setPicked(null)} />
      <MobileSearchOverlay
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onPick={setPicked}
      />
      <FilterSheet
        open={filterOpen}
        filters={filters}
        onApply={(next) => {
          setFilters(next);
          setFilterOpen(false);
        }}
        onClose={() => setFilterOpen(false)}
      />
      <EtaSheet
        open={etaOpen}
        candidateIds={candidateIds}
        totalCandidates={totalCandidates}
        onApplied={setEtaResults}
        onClose={() => setEtaOpen(false)}
      />
    </div>
  );
}
