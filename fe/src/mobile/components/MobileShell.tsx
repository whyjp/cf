import { useState } from "react";
import { TopBar } from "./TopBar";
import { MobileMap } from "./MobileMap";
import { BottomSheet } from "./BottomSheet";
import { MobileCampList } from "./MobileCampList";
import { DetailSheet } from "./DetailSheet";
import { MobileSearchOverlay } from "./MobileSearchOverlay";
import { LocationChip } from "./LocationChip";
import { useSites } from "../../shared/hooks/useSites";
import type { Filters } from "../../shared/filters";

/**
 * MobileShell — h-dvh flex column.
 *
 * Layout:
 *   [TopBar 56dp]
 *   [main relative — MobileMap(absolute inset-0)
 *                  + LocationChip(absolute top-3 right-3 z-10)
 *                  + BottomSheet(absolute bottom)]
 *   [DetailSheet — fixed inset-0 z-50, picked!=null 일 때만]
 *   [MobileSearchOverlay — fixed inset-0 z-50, searchOpen 일 때만]
 *
 * picked / searchOpen 은 둘 다 Shell 에서 관리 — DetailSheet 와 Overlay
 * 가 모두 z-50 풀스크린이라 동시에 열리면 z-index 우열만으론 어색하다.
 * Overlay 의 onPick → setPicked + onClose 동시 호출로 자연 전환되므로
 * 두 시트가 동시에 활성되는 일은 없다 (Plan 패턴).
 *
 * Filters 는 C2 의 partial 그대로 — C4 가 진짜 필터를 채우면 cast 제거.
 */
export function MobileShell() {
  const [filters] = useState<Filters>(
    { region: new Set() } as Filters,
  );
  const { rows, loading, err } = useSites(filters);
  const [picked, setPicked] = useState<string | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);

  return (
    <div className="h-dvh flex flex-col">
      <TopBar onSearch={() => setSearchOpen(true)} />
      <main className="flex-1 relative overflow-hidden">
        <MobileMap rows={rows} onPick={setPicked} />
        <div className="absolute top-3 right-3 z-10">
          <LocationChip />
        </div>
        <BottomSheet initial="peek">
          <div
            className="px-4 py-3 border-b flex items-center gap-2"
            style={{ borderColor: "rgba(26,26,23,0.12)" }}
          >
            <span className="display font-semibold text-base num">
              {loading ? "…" : rows.length.toLocaleString()}
            </span>
            <span className="text-sm text-stone-500">곳</span>
            {err && (
              <span className="ml-auto text-xs text-red-600" title={err}>
                error
              </span>
            )}
          </div>
          <MobileCampList rows={rows} onPick={setPicked} />
        </BottomSheet>
      </main>
      <DetailSheet id={picked} onClose={() => setPicked(null)} />
      <MobileSearchOverlay
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onPick={setPicked}
      />
    </div>
  );
}
