/**
 * Origin: fe/index.legacy.html:1374-1424. EtaBar + minutesFrom helper.
 */

export interface EtaBarSummary {
  within_count?: number;
  checked?: number;
}

export interface EtaBarProps {
  origin: string;
  setOrigin: (v: string) => void;
  hours: number;
  setHours: (n: number) => void;
  mins: number;
  setMins: (n: number) => void;
  etaActive: boolean;
  setEtaActive: (v: boolean) => void;
  onApply: () => void;
  onClear: () => void;
  loading: boolean;
  summary: EtaBarSummary | null;
  candidateCount: number;
  hardCap: number;
}

export function EtaBar({
  origin,
  setOrigin,
  hours,
  setHours,
  mins,
  setMins,
  etaActive,
  setEtaActive,
  onApply,
  onClear,
  loading,
  summary,
  candidateCount,
  hardCap,
}: EtaBarProps) {
  const tooMany = candidateCount > hardCap;
  return (
    <div
      className="flex items-center gap-2 flex-wrap p-3 rounded-xl border hairline"
      style={{ background: "rgba(44,74,62,0.04)" }}
    >
      <span className="text-[10px] uppercase tracking-[0.2em] text-stone-500 mr-1 shrink-0">
        출발지 ETA
      </span>
      <input
        value={origin}
        onChange={(e) => setOrigin(e.target.value)}
        placeholder="예: 강남역, 서울역, 수원시청"
        className="text-sm bg-[color:var(--paper)] border hairline rounded-md px-2.5 py-1.5 outline-none focus:border-stone-900 min-w-[180px] flex-1 max-w-[260px]"
      />
      <span className="text-[10px] text-stone-500">최대</span>
      <input
        type="number"
        min="0"
        max="23"
        value={hours}
        onChange={(e) =>
          setHours(Math.max(0, Math.min(23, parseInt(e.target.value || "0", 10))))
        }
        className="text-sm bg-[color:var(--paper)] border hairline rounded-md w-14 px-2 py-1.5 num text-right outline-none focus:border-stone-900"
      />
      <span className="text-[11px] text-stone-500">시</span>
      <input
        type="number"
        min="0"
        max="59"
        step="5"
        value={mins}
        onChange={(e) =>
          setMins(Math.max(0, Math.min(59, parseInt(e.target.value || "0", 10))))
        }
        className="text-sm bg-[color:var(--paper)] border hairline rounded-md w-14 px-2 py-1.5 num text-right outline-none focus:border-stone-900"
      />
      <span className="text-[11px] text-stone-500">분</span>
      <button
        onClick={onApply}
        disabled={loading || !origin.trim() || candidateCount === 0}
        className="btn btn-primary"
      >
        {loading ? "계산 중…" : `ETA 적용 (${candidateCount}곳)`}
      </button>
      {etaActive && (
        <button onClick={onClear} className="btn">
          해제
        </button>
      )}
      <label
        className="flex items-center gap-1.5 ml-1 text-[11px] text-stone-600 cursor-pointer select-none"
        title="시간 초과 캠프를 숨기기"
      >
        <input
          type="checkbox"
          checked={etaActive}
          onChange={(e) => setEtaActive(e.target.checked)}
          className="accent-stone-700"
        />
        시간 내만
      </label>
      {tooMany && (
        <span
          className="text-[11px] num"
          style={{ color: "var(--ember)" }}
          title="필터로 좁힌 뒤 다시 시도하세요"
        >
          ⚠ {candidateCount}곳 — 먼저 지역/컨셉 필터로 {hardCap}곳 이하로 좁히세요
        </span>
      )}
      {summary && !tooMany && (
        <span className="text-[11px] text-stone-500 ml-auto num">
          {summary.within_count}/{summary.checked}{" "}
          <span className="text-stone-400">접근가능</span>
        </span>
      )}
    </div>
  );
}

/** Origin: fe/index.legacy.html:1424. */
export function minutesFrom(h: number, m: number): number {
  return Math.max(0, (h | 0) * 60 + (m | 0));
}
