import { useMemo } from "react";
import { useDetail } from "../../shared/hooks/useDetail";
import type { EtaResult, FeaturedAxis } from "../../shared/types";
import { Chip, EtaBadge, prettyTag, tagHue } from "./atoms";
import { Stat } from "./atoms";
import { MiniMap } from "./MiniMap";

/**
 * Right-side slide-in panel with map + photos + categories + facilities
 * + reviews. Renders nothing when `id` is null. Loading state is a
 * scaffold with just a close button + spinner text.
 *
 * Origin: fe/index.legacy.html:1207-1369.
 */
export interface DetailPanelProps {
  id: string | null;
  onClose: () => void;
  eta?: EtaResult | null;
  axes: FeaturedAxis[];
}

interface ReviewLite {
  user?: string;
  season?: string;
  userType?: string;
  numOfDays?: number;
  score?: number | null;
  text: string;
}

interface PhotoLite {
  url: string;
  thumb: string;
}

export function DetailPanel({ id, onClose, eta, axes }: DetailPanelProps) {
  const axisByKo = useMemo(() => {
    const m = new Map<string, FeaturedAxis>();
    for (const a of axes || []) m.set(a.ko, a);
    return m;
  }, [axes]);
  const data = useDetail(id);
  if (!id) return null;
  if (!data)
    return (
      <div
        data-panel="detail"
        className="fixed inset-y-0 right-0 w-[420px] bg-stone-50 border-l hairline shadow-xl p-6 z-[1100] overflow-auto"
      >
        <button onClick={onClose} className="btn">
          닫기
        </button>
        <div className="mt-6 text-stone-500">불러오는 중…</div>
      </div>
    );

  // Detail rows are loose — extract optional fields with safe casts.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const d = data as any;
  const cats: string[] = d.categories || [];
  const facs: string[] = d.facilities || [];
  const photos: PhotoLite[] = d.photos || [];
  const reviewsTop: ReviewLite[] = d.reviews_top || [];
  const hashtags: string[] = d.hashtags || [];
  return (
    <div
      data-panel="detail"
      className="fixed inset-y-0 right-0 w-[420px] bg-[color:var(--paper)] border-l hairline shadow-2xl z-[1100] overflow-auto topo"
    >
      <div className="p-5 border-b hairline flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-[0.2em] text-stone-500">상세</span>
        <button onClick={onClose} className="btn">
          ×
        </button>
      </div>
      <div className="p-5 space-y-5">
        <div>
          <div className="text-[11px] num text-stone-500">
            {d.region_sido || "—"} {d.region_sigungu || ""}
          </div>
          <h2 className="display text-2xl font-bold leading-tight">
            {d.name || "(이름 미상)"}
          </h2>
          {d.address && <div className="text-xs text-stone-600 mt-1">{d.address}</div>}
          {eta && eta.minutes != null && (
            <div className="mt-2">
              <EtaBadge minutes={eta.minutes} within={eta.within} error={eta.error} />
            </div>
          )}
          <div className="flex flex-wrap gap-2 mt-3">
            {d.name && (
              <a
                href={`https://map.naver.com/p/search/${encodeURIComponent(
                  [d.region_sigungu, d.name].filter(Boolean).join(" "),
                )}`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn inline-block"
                style={{ background: "#03C75A", color: "#fff", borderColor: "#03C75A" }}
                title="네이버 지도에서 위치 확인"
              >
                📍 네이버 지도 ↗
              </a>
            )}
            {d.url && (
              <a
                href={d.url}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-primary inline-block"
              >
                camfit 원본 열기 ↗
              </a>
            )}
          </div>
        </div>
        <MiniMap lat={d.lat} lon={d.lon} name={d.name} />
        <div className="grid grid-cols-3 gap-3">
          <Stat
            label="가격"
            value={d.priceStartFrom ? d.priceStartFrom.toLocaleString() + "~" : "—"}
            sub={d.priceEndTo ? d.priceEndTo.toLocaleString() : null}
          />
          <Stat
            label="리뷰"
            value={d.numOfReviews ? d.numOfReviews.toLocaleString() : "—"}
          />
          <Stat
            label="북마크"
            value={d.bookmarkCount ? d.bookmarkCount.toLocaleString() : "—"}
          />
        </div>
        {d.brief && (
          <div className="text-[13px] text-stone-700 italic border-l-2 pl-3 hairline">
            {d.brief}
          </div>
        )}
        {d.locationBrief && (
          <div className="text-[12px] text-stone-600">📍 {d.locationBrief}</div>
        )}
        {(d.priceStartFrom || d.priceEndTo) && (
          <div className="text-[13px] num">
            <span className="text-stone-500">가격</span>{" "}
            <span className="font-semibold">
              {d.priceStartFrom ? d.priceStartFrom.toLocaleString() : "?"}원~
              {d.priceEndTo ? ` ${d.priceEndTo.toLocaleString()}원` : ""}
            </span>
          </div>
        )}
        {d.numOfReviews ? (
          <div className="text-[12px] text-stone-600">
            ⭐ <span className="num font-semibold">{d.numOfReviews}</span> 리뷰
            {d.bookmarkCount ? (
              <span className="ml-2">🔖 {d.bookmarkCount.toLocaleString()}</span>
            ) : null}
          </div>
        ) : null}
        {photos.length > 0 && (
          <div className="grid grid-cols-3 gap-1.5">
            {photos.slice(0, 6).map((p, i) => (
              <a
                key={i}
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block aspect-square overflow-hidden rounded-md border hairline"
              >
                <img src={p.thumb} alt="" className="w-full h-full object-cover" loading="lazy" />
              </a>
            ))}
          </div>
        )}
        {cats.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-stone-500 mb-2">
              카테고리
            </div>
            <div className="flex flex-wrap gap-1.5">
              {cats.map((c) => {
                const axis = axisByKo.get(c);
                return axis ? (
                  <Chip key={c} tone={axis.tone}>
                    {axis.icon} {c}
                  </Chip>
                ) : (
                  <span
                    key={c}
                    className="chip"
                    style={{
                      background: tagHue(c) + "14",
                      color: tagHue(c),
                      borderColor: tagHue(c) + "33",
                    }}
                  >
                    {prettyTag(c)}
                  </span>
                );
              })}
            </div>
          </div>
        )}
        {facs.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-stone-500 mb-2">
              시설 ({facs.length})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {facs.slice(0, 30).map((f) =>
                f === "trampoline" ? (
                  <Chip key={f} tone="bark">
                    🤸 {f}
                  </Chip>
                ) : (
                  <span
                    key={f}
                    className="chip"
                    style={{
                      background: tagHue(f) + "14",
                      color: tagHue(f),
                      borderColor: tagHue(f) + "33",
                    }}
                  >
                    {f}
                  </span>
                ),
              )}
            </div>
          </div>
        )}
        {hashtags.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-stone-500 mb-2">
              해시태그
            </div>
            <div className="flex flex-wrap gap-1">
              {hashtags.slice(0, 14).map((h) => (
                <span key={h} className="text-[11px] text-stone-600">
                  #{h}
                </span>
              ))}
              {hashtags.length > 14 && (
                <span className="text-[11px] text-stone-400">+{hashtags.length - 14}</span>
              )}
            </div>
          </div>
        )}
        {d.description && (
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-stone-500 mb-2">소개</div>
            <div className="text-[12.5px] leading-relaxed text-stone-700 max-h-64 overflow-y-auto whitespace-pre-line border hairline rounded-md p-3 bg-[color:var(--paper)]">
              {d.description}
            </div>
          </div>
        )}
        {reviewsTop.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-stone-500 mb-2">
              리뷰 미리보기{" "}
              {d.reviews_total ? `· 전체 ${d.reviews_total.toLocaleString()}` : ""}
            </div>
            <div className="space-y-2">
              {reviewsTop.map((rv, i) => (
                <div
                  key={i}
                  className="border hairline rounded-md p-2.5 text-[12px] bg-[color:var(--paper)]"
                >
                  <div className="flex items-center gap-2 text-[10px] text-stone-500 mb-1.5">
                    <span className="font-semibold text-stone-700">{rv.user}</span>
                    {rv.season && <span>· {rv.season}</span>}
                    {rv.userType && <span>· {rv.userType}</span>}
                    {rv.numOfDays && <span>· {rv.numOfDays}박</span>}
                    {rv.score != null && <span className="num ml-auto">⭐ {rv.score}</span>}
                  </div>
                  <div className="text-stone-700 leading-relaxed line-clamp-5 whitespace-pre-line">
                    {rv.text.length > 320 ? rv.text.slice(0, 320) + "…" : rv.text}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {d.contact && <div className="text-[12px] text-stone-600">📞 {d.contact}</div>}
      </div>
    </div>
  );
}
