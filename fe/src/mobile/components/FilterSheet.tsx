import { useEffect, useState } from "react";
import { useFacets } from "../../shared/hooks/useFacets";
import { useFeaturedAxes } from "../../shared/hooks/useFeaturedAxes";
import type { Filters } from "../../shared/filters";

/**
 * FilterSheet — 풀스크린 (fixed inset-0 z-50) 모달 필터.
 *
 * 패턴 (DetailSheet/MobileSearchOverlay 와 동일):
 *   - open=false → null 반환 (DOM out → 다음 오픈 때 깨끗한 draft 시작).
 *   - draft 패턴: 본 시트 내부의 useState 가 사용자 변경을 모은다.
 *     "적용" 누르면 onApply(draft) 한 번에 부모 filters 를 교체.
 *     "← 닫기" 는 draft 를 버리고 onClose — 부모 filters 는 유지.
 *
 * filters prop 이 바뀌면 (외부에서 reset 등) draft 도 동기화.
 *
 * 첫 컷 범위 (review note B2 / plan Step 3 ⚠️):
 *   - 지역 (sido) 토글 — facets.regions 의 unique sido 목록.
 *   - 대표축 — 표시만, 토글 X (다음 sprint 에서 has_<axisId> 토글 연결).
 *
 * 후속 sprint (C5/C6 또는 같은 PR 의 follow-up commit):
 *   - concept axes (view, facility, kidsFacility, surface, space, parking,
 *     audience, vibe) — facets.concept_axes 구조 확정 후 동일 패턴으로 추가.
 *   - terrain / collection / facilityRaw / management — 데스크톱 FilterBar
 *     의 9슬롯 모두 mirroring.
 *
 * Origin: plans/2026-05-10-fe-vite-and-mobile.md Task C4 Step 3.
 */
interface Props {
  open: boolean;
  filters: Filters;
  onApply: (next: Filters) => void;
  onClose: () => void;
}

export function FilterSheet({ open, filters, onApply, onClose }: Props) {
  const { data: facets } = useFacets();
  const axes = useFeaturedAxes();
  const [draft, setDraft] = useState<Filters>(filters);

  // 시트가 새로 열릴 때마다 부모 filters 로 draft 초기화 (이전 세션의
  // 미적용 변경이 잔류하지 않도록).
  useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  // Esc → 닫기 (대형 모바일 + 외장 키보드 케이스 대비. DetailSheet 와 동일).
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const toggleRegion = (sido: string) => {
    setDraft((d) => {
      const next = new Set(d.region);
      if (next.has(sido)) next.delete(sido);
      else next.add(sido);
      return { ...d, region: next };
    });
  };

  // 지역: facets.regions 는 (sido, sigungu) 페어이므로 sido unique 로 압축.
  const sidos = Array.from(
    new Set((facets.regions ?? []).map((r) => r.sido).filter(Boolean)),
  );

  return (
    <div
      className="fixed inset-0 z-50 bg-white flex flex-col"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <header
        className="h-14 px-4 flex items-center justify-between border-b flex-shrink-0"
        style={{ borderColor: "rgba(26,26,23,0.12)" }}
      >
        <button
          onClick={onClose}
          aria-label="close"
          className="text-xl leading-none w-10 h-10 flex items-center justify-center -ml-2"
        >
          ←
        </button>
        <h2 className="display font-semibold">필터</h2>
        <button
          onClick={() => onApply(draft)}
          className="px-3 py-1.5 rounded-md font-medium"
          style={{ background: "var(--moss)", color: "#f7f4e8" }}
        >
          적용
        </button>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6">
        <section>
          <h3 className="text-sm font-semibold mb-2">지역</h3>
          {sidos.length === 0 ? (
            <p className="text-xs text-stone-500">지역 정보를 불러오는 중…</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {sidos.map((s) => {
                const active = draft.region.has(s);
                return (
                  <button
                    key={s}
                    onClick={() => toggleRegion(s)}
                    className="px-3 py-1.5 rounded-full text-sm border"
                    style={{
                      background: active ? "var(--moss)" : "var(--paper)",
                      color: active ? "#f7f4e8" : "var(--ink)",
                      borderColor: "rgba(26,26,23,0.18)",
                    }}
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <section>
          <h3 className="text-sm font-semibold mb-2">대표축</h3>
          {axes.length === 0 ? (
            <p className="text-xs text-stone-500">대표축이 없습니다.</p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {axes.map((a) => (
                <span
                  key={a.id}
                  className="px-3 py-1.5 rounded-full text-sm border opacity-90"
                  style={{ borderColor: "rgba(26,26,23,0.18)" }}
                >
                  {a.icon ?? "•"} {a.name ?? a.ko}
                </span>
              ))}
            </div>
          )}
          <p className="text-xs text-stone-500 mt-2">
            대표축 토글은 후속 sprint 에서 연결됩니다.
          </p>
        </section>

        {/* concept axes / view / facility 등은 동일 패턴으로 후속 commit
            에서 추가 — facets.concept_axes 구조 확정 후. */}
      </div>
    </div>
  );
}
