import { useEffect, useRef, useState } from "react";
import { API_BASE } from "../../shared/api";
import type { FeaturedAxis, Site } from "../../shared/types";

/**
 * Semantic search via /sites/search?q=… — debounced 250ms.
 *
 * Result shape mirrors `_camp_to_fe_row` (id/name/sido/sigungu/has_<axis>).
 *
 * Origin: fe/index.legacy.html:1063-1140.
 */
export interface SearchBoxProps {
  onPickResult: (results: Site[]) => void;
  axes: FeaturedAxis[];
}

export function SearchBox({ onPickResult, axes }: SearchBoxProps) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Site[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const tRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (tRef.current) clearTimeout(tRef.current);
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    setBusy(true);
    tRef.current = setTimeout(() => {
      fetch(`${API_BASE}/sites/search?q=${encodeURIComponent(q.trim())}&k=20`)
        .then((r) => r.json())
        .then((d) => {
          const arr: Site[] = Array.isArray(d) ? d : (d.results || d.hits || []);
          setResults(arr);
          setOpen(true);
        })
        .catch(() => setResults([]))
        .finally(() => setBusy(false));
    }, 250);
  }, [q]);

  const apply = (asList: Site[]) => {
    onPickResult(asList);
    setOpen(false);
  };

  return (
    <div className="relative">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 180)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && results.length > 0) {
            e.preventDefault();
            apply(results);
          }
          if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        placeholder="🔎 시멘틱 검색 (예: 계곡 옆 키즈)"
        className="text-sm bg-[color:var(--paper)] border hairline rounded-md px-3 py-1.5 outline-none focus:border-stone-900 w-[260px]"
      />
      {open && (results.length > 0 || busy) && (
        <div className="absolute z-[1200] mt-1 w-[320px] max-h-80 overflow-auto bg-[color:var(--paper)] border hairline rounded-md shadow-lg right-0">
          {busy && results.length === 0 && (
            <div className="px-3 py-2 text-[12px] text-stone-500">검색 중…</div>
          )}
          {results.length > 0 && (
            <button
              onMouseDown={(e) => {
                e.preventDefault();
                apply(results);
              }}
              className="w-full text-left px-3 py-2 hover:bg-stone-200/60 border-b hairline text-[12px] font-semibold text-[color:var(--moss-deep)]"
            >
              📍 검색결과 {results.length}건 지도에 적용
            </button>
          )}
          {results.map((n, i) => (
            <button
              key={n.id || i}
              onMouseDown={(e) => {
                e.preventDefault();
                apply([n]);
              }}
              className="w-full text-left px-3 py-2 hover:bg-stone-200/60 border-b hairline last:border-b-0 flex items-center gap-2"
            >
              <span className="text-[11px] num text-stone-500 w-5">{i + 1}</span>
              <div className="min-w-0 flex-1">
                <div className="text-[12.5px] truncate font-medium">{n.name || "(이름 미상)"}</div>
                <div className="text-[10.5px] text-stone-500 truncate">
                  {(n.sido || "") + " " + (n.sigungu || "")}
                  {(axes || []).map((a) => (n[`has_${a.id}`] ? ` · ${a.icon}` : "")).join("")}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
