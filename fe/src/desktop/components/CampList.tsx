import { useMemo } from "react";
import { formatKm } from "../../shared/geo";
import type { EtaResult, FeaturedAxis, Site } from "../../shared/types";
import { Chip, EtaBadge, PinDots, buildFeaturedNames, prettyTag, tagHue } from "./atoms";

/**
 * Card-style list of camps. Selected card gets a heavier border.
 * Featured-axis chips render first; long-tail categories drop the names
 * already shown as axis chips and cap at 4 with a "+N" overflow tail.
 *
 * Origin: fe/index.legacy.html:1142-1202.
 */
export interface CampListProps {
  rows: Site[];
  onPick: (id: string) => void;
  selectedId: string | null;
  etaMap?: Record<string, EtaResult> | null;
  axes: FeaturedAxis[];
}

export function CampList({ rows, onPick, selectedId, etaMap, axes }: CampListProps) {
  const featuredNames = useMemo(() => buildFeaturedNames(axes), [axes]);
  return (
    <div className="grid gap-2">
      {rows.map((r) => {
        const eta = etaMap?.[r.id];
        const cats = (r.categories || []) as string[];
        const longTail = cats.filter((n) => !featuredNames.has(n));
        return (
          <div
            key={r.id}
            data-camp-card
            data-camp-id={r.id}
            onClick={() => onPick(r.id)}
            className={`card text-left p-3 cursor-pointer ${selectedId === r.id ? "border-stone-900" : ""}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="text-[11px] text-stone-500 num flex items-center gap-1.5">
                  <span>
                    {r.sido || "—"} {r.sigungu || ""}
                  </span>
                  {r._distanceKm != null && (
                    <span
                      title="내 위치로부터 직선거리"
                      className="chip"
                      style={{
                        padding: "0 6px",
                        fontSize: "10px",
                        borderColor: "#cfdcc9",
                        color: "#2c4a3e",
                        background: "rgba(44,74,62,0.06)",
                      }}
                    >
                      🧭 {formatKm(r._distanceKm)}
                    </span>
                  )}
                  {(r.lat == null || r.lon == null) && (
                    <span
                      title="정확한 좌표 미확인 — 지도에서 제외"
                      className="chip"
                      style={{
                        padding: "0 4px",
                        fontSize: "9px",
                        borderColor: "#d6cfc2",
                        color: "#9a8b6b",
                        background: "#fdf8eb",
                      }}
                    >
                      📍?
                    </span>
                  )}
                </div>
                <div className="font-semibold leading-snug truncate">{r.name}</div>
                {r.address ? (
                  <div className="text-[11px] text-stone-500 truncate mt-0.5">
                    {r.address as string}
                  </div>
                ) : null}
                <div className="mt-1.5 flex flex-wrap gap-1 items-center">
                  {(axes || []).map((a) =>
                    r[`has_${a.id}`] ? (
                      <Chip key={a.id} tone={a.tone}>
                        {a.icon} {a.ko}
                      </Chip>
                    ) : null,
                  )}
                  {longTail.slice(0, 4).map((n) => (
                    <span
                      key={"c-" + n}
                      className="chip"
                      style={{
                        background: tagHue(n) + "14",
                        color: tagHue(n),
                        borderColor: tagHue(n) + "33",
                      }}
                    >
                      {prettyTag(n)}
                    </span>
                  ))}
                  {longTail.length > 4 && (
                    <span className="text-[10px] text-stone-500">+{longTail.length - 4}</span>
                  )}
                  {(axes || []).every((a) => !r[`has_${a.id}`]) && cats.length === 0 && (
                    <span className="text-[11px] text-stone-400">—</span>
                  )}
                  {eta && (
                    <EtaBadge minutes={eta.minutes} within={eta.within} error={eta.error} />
                  )}
                </div>
              </div>
              <PinDots row={r} axes={axes} />
            </div>
          </div>
        );
      })}
      {rows.length === 0 && (
        <div className="text-sm text-stone-500 px-1 py-4">조건에 맞는 캠프가 없습니다.</div>
      )}
    </div>
  );
}
