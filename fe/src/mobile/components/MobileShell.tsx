import { useState } from "react";
import { TopBar } from "./TopBar";
import { MobileMap } from "./MobileMap";
import { BottomSheet } from "./BottomSheet";
import { useSites } from "../../shared/hooks/useSites";
import type { Filters } from "../../shared/filters";

/**
 * MobileShell — h-dvh flex column.
 *
 * Layout:
 *   [TopBar 56dp]
 *   [main relative — MobileMap(absolute inset-0) + BottomSheet(absolute bottom)]
 *
 * C2: useSites + initial empty filters (region: empty Set). visibleRows
 * (B2) 는 C4 의 FilterSheet 가 들어올 때 합류 — C2 first cut 은 rows
 * 그대로 패스해서 핀/카드를 그린다.
 *
 * Filters 타입은 Set 슬롯이 잔뜩이라 빈 객체에서 단계적으로 채울 수
 * 없다. 여기서는 region 만 초기화한 partial 을 `as Filters` 로 cast —
 * useSites 본문이 region.size + setSerialize 만 보고 동작하므로 안전.
 * C4 가 진짜 필터를 채우면 cast 제거 가능.
 */
export function MobileShell() {
  const [filters] = useState<Filters>(
    { region: new Set() } as Filters,
  );
  const { rows, loading, err } = useSites(filters);
  // setPicked 는 C3 의 DetailSheet 가 부착될 때 의미를 갖는다. C2 에서는
  // 마커 탭 → 콘솔 흐름만 확인하지만, 시그니처는 미리 잡아둔다.
  const [, setPicked] = useState<string | null>(null);

  return (
    <div className="h-dvh flex flex-col">
      <TopBar />
      <main className="flex-1 relative overflow-hidden">
        <MobileMap rows={rows} onPick={setPicked} />
        <BottomSheet initial="peek">
          <div
            className="px-4 py-3 border-b flex items-center gap-2"
            style={{ borderColor: "rgba(26,26,23,0.12)" }}
          >
            <span className="display font-semibold text-base">
              {loading ? "…" : rows.length.toLocaleString()}
            </span>
            <span className="text-sm text-stone-500">곳</span>
            {err && (
              <span className="ml-auto text-xs text-red-600" title={err}>
                error
              </span>
            )}
          </div>
          <div>
            {rows.slice(0, 30).map((r) => (
              <button
                key={r.id}
                onClick={() => setPicked(r.id)}
                className="w-full text-left px-4 py-3 border-b active:bg-stone-100"
                style={{ borderColor: "rgba(26,26,23,0.06)" }}
              >
                <div className="font-medium text-sm">{r.name}</div>
                <div className="text-xs text-stone-500 mt-0.5">
                  {r.sido} · {r.sigungu}
                </div>
              </button>
            ))}
          </div>
        </BottomSheet>
      </main>
    </div>
  );
}
