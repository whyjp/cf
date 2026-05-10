import { useEffect, useRef, useState } from "react";
import { getJson } from "../../shared/api";
import type { Site } from "../../shared/types";

/**
 * MobileSearchOverlay — 풀스크린 검색 오버레이.
 *
 * open=false 일 때 null 반환으로 DOM 자체가 빠지므로 input 의 잔류
 * 포커스/value 가 다음 오픈 때 깨끗하게 시작된다.
 *
 * 200ms debounce — 한국어 IME 조합 중에는 onChange 가 자주 튀어서
 * 디바운스 없으면 /sites/search 가 폭발한다. 200ms 는 체감 즉시감과
 * 서버 부하 사이의 균형 (Plan Step 4).
 *
 * 결과 클릭 → onPick(id) 후 즉시 onClose: 그래야 DetailSheet 가
 * SearchOverlay 위에 또 깔리지 않고 한 화면씩 전환된다 (z-50 동등).
 */
interface Props {
  open: boolean;
  onClose: () => void;
  onPick: (id: string) => void;
}

export function MobileSearchOverlay({ open, onClose, onPick }: Props) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Site[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!q.trim()) {
      setResults([]);
      return;
    }
    setLoading(true);
    const t = setTimeout(() => {
      getJson<Site[]>("/sites/search", { q, k: 20 })
        .then((arr) => setResults(Array.isArray(arr) ? arr : []))
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(t);
  }, [q]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 bg-white flex flex-col"
      style={{
        paddingTop: "env(safe-area-inset-top)",
        paddingBottom: "env(safe-area-inset-bottom)",
      }}
    >
      <header
        className="h-14 px-2 flex items-center gap-2 border-b flex-shrink-0"
        style={{ borderColor: "var(--border-faint)" }}
      >
        <button
          onClick={onClose}
          aria-label="close"
          className="text-xl px-3 leading-none w-10 h-10 flex items-center justify-center"
        >
          ←
        </button>
        <input
          ref={inputRef}
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="캠핑장 검색"
          className="flex-1 h-10 px-2 outline-none text-base bg-transparent"
        />
      </header>
      <div className="flex-1 overflow-y-auto">
        {loading && <div className="p-4 text-stone-500">검색 중…</div>}
        {!loading &&
          results.map((r) => (
            <button
              key={r.id}
              className="w-full text-left px-4 py-3 border-b active:bg-stone-50"
              style={{ borderColor: "rgba(26,26,23,0.06)" }}
              onClick={() => {
                onPick(r.id);
                onClose();
              }}
            >
              <div className="font-semibold">{r.name}</div>
              <div className="text-xs text-stone-500">
                {r.sido} · {r.sigungu}
              </div>
            </button>
          ))}
        {!loading && q.trim() && results.length === 0 && (
          <div className="p-4 text-stone-500 text-sm">결과 없음</div>
        )}
      </div>
    </div>
  );
}
