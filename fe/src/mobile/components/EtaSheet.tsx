import { useEffect, useState } from "react";
import { useEtaBatch } from "../../shared/hooks/useEtaBatch";
import { useUserLocation } from "../../shared/hooks/useUserLocation";
import { ETA_HARD_CAP } from "../../shared/constants";
import type { EtaResult } from "../../shared/types";

/**
 * EtaSheet — 풀스크린 (fixed inset-0 z-50) 모달 ETA 계산.
 *
 * 동작:
 *   1. useUserLocation 의 coords 가 있어야 적용 가능 (없으면 disabled).
 *   2. hours/mins select → max_minutes 합산.
 *   3. 적용 → useEtaBatch.apply({ origin: "lat,lon", ids, max_minutes }).
 *      - origin 변환 ⚠️ : BE `/eta/batch` 는 `origin: str` 만 받는다
 *        (review note A4). useEtaBatch 의 BatchInput 타입도 string 으로
 *        고정됐으므로 여기서 "<lat>,<lon>" 으로 캐스팅.
 *   4. 결과 받으면 onApplied(results) 로 부모에게 전달 → 부모는
 *      etaResults state 에 저장 후 visibleRows 필터링에 사용.
 *
 * candidateIds 상한 (review note B2):
 *   부모가 rows.slice(0, ETA_HARD_CAP) 으로 미리 잘라서 넘기므로 이 시트는
 *   계산만 한다. 안내 문구만 노출 — "후보 N 곳 (상한 300)" + 잘렸을 경우
 *   "초과 시 처음 300곳만 계산" warning. 상한은 ETA_HARD_CAP 상수.
 *
 * results: useEtaBatch 가 EtaResult Record 로 인덱스해 둠. onApplied 에는
 * 그대로 흘려보내고, 부모는 r.id 로 within 만 체크하면 된다.
 *
 * Origin: plans/2026-05-10-fe-vite-and-mobile.md Task C4 Step 4.
 */
interface Props {
  open: boolean;
  /** rows.slice(0, ETA_HARD_CAP).map(r => r.id) — 부모가 잘라서 넘김. */
  candidateIds: string[];
  /** 잘리기 전 전체 후보 수 — 안내 메시지에 활용. */
  totalCandidates: number;
  onApplied: (results: Record<string, EtaResult> | null) => void;
  onClose: () => void;
}

export function EtaSheet({
  open,
  candidateIds,
  totalCandidates,
  onApplied,
  onClose,
}: Props) {
  const { coords, status, refresh } = useUserLocation();
  const [hours, setHours] = useState(2);
  const [mins, setMins] = useState(0);
  const { apply, loading, results, err, clear } = useEtaBatch();

  // results 가 채워지면 부모로 전달 (apply 가 비동기이므로 별도 effect).
  useEffect(() => {
    if (results) onApplied(results);
  }, [results, onApplied]);

  // Esc → 닫기.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  const submit = async () => {
    if (!coords) return;
    const max_minutes = hours * 60 + mins || null;
    // ⚠️ A4 fix: BE 는 origin: str 만 받는다. UserCoords → "lat,lon" 변환.
    const origin = `${coords.lat},${coords.lon}`;
    try {
      await apply({ origin, ids: candidateIds, max_minutes });
      onClose();
    } catch {
      // useEtaBatch 가 err state 로 surface 하므로 silent.
    }
  };

  const reset = () => {
    clear();
    onApplied(null);
    onClose();
  };

  const truncated = totalCandidates > ETA_HARD_CAP;

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
        <h2 className="display font-semibold">ETA</h2>
        <button
          onClick={submit}
          disabled={!coords || loading || candidateIds.length === 0}
          className="px-3 py-1.5 rounded-md font-medium disabled:opacity-50"
          style={{ background: "var(--moss)", color: "#f7f4e8" }}
        >
          {loading ? "계산 중…" : "적용"}
        </button>
      </header>
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
        {!coords && (
          <div className="text-sm text-stone-600 space-y-2">
            <div>
              내 위치 권한이 필요합니다 (현재: <span className="num">{status}</span>).
            </div>
            <button
              onClick={refresh}
              className="px-3 py-1.5 rounded-md text-sm border"
              style={{ borderColor: "rgba(26,26,23,0.18)" }}
            >
              위치 다시 요청
            </button>
          </div>
        )}

        <section>
          <label className="text-sm font-semibold">최대 이동 시간</label>
          <div className="flex gap-3 mt-2">
            <select
              value={hours}
              onChange={(e) => setHours(+e.target.value)}
              className="border rounded px-2 py-1.5 num"
              style={{ borderColor: "rgba(26,26,23,0.18)" }}
            >
              {Array.from({ length: 9 }).map((_, i) => (
                <option key={i} value={i}>
                  {i} 시간
                </option>
              ))}
            </select>
            <select
              value={mins}
              onChange={(e) => setMins(+e.target.value)}
              className="border rounded px-2 py-1.5 num"
              style={{ borderColor: "rgba(26,26,23,0.18)" }}
            >
              {[0, 15, 30, 45].map((m) => (
                <option key={m} value={m}>
                  {m} 분
                </option>
              ))}
            </select>
          </div>
        </section>

        <section className="text-xs text-stone-600 space-y-1">
          <div>
            후보 <span className="num">{candidateIds.length}</span> 곳 (상한{" "}
            <span className="num">{ETA_HARD_CAP}</span>)
          </div>
          {truncated && (
            <div className="text-[color:var(--ember)]">
              총 {totalCandidates.toLocaleString()} 곳 중 처음 {ETA_HARD_CAP}
              곳만 계산합니다. 지역/컨셉 필터로 줄이면 더 정확해집니다.
            </div>
          )}
        </section>

        {err && (
          <div className="text-sm text-[color:var(--ember)]">에러: {err}</div>
        )}

        {results && (
          <button
            onClick={reset}
            className="text-sm underline underline-offset-2 text-stone-600"
          >
            ETA 결과 초기화
          </button>
        )}
      </div>
    </div>
  );
}
