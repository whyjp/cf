import { useUserLocation } from "../../shared/hooks/useUserLocation";
import { haversineKm, formatKm } from "../../shared/geo";
import type { Site } from "../../shared/types";

/**
 * MobileCampList — BottomSheet body 의 카드 목록.
 *
 * useUserLocation 의 coords 가 채워져 있고 row 가 lat/lon 을 둘 다 들고
 * 있을 때만 거리 뱃지를 단다 (그 외엔 null → 우측 라벨 미표시).
 *
 * 스크롤은 BottomSheet 의 overflow-y-auto 가 책임지므로 ul 자체엔 max-h
 * 를 두지 않는다 — 시트 높이가 결정해야 peek/half/full 모드와 일관.
 *
 * onPick 은 카드 전체 영역 → MobileShell 의 setPicked 로 흘러서
 * DetailSheet 가 열린다. active:bg-stone-50 으로 탭 피드백.
 */
interface Props {
  rows: Site[];
  onPick: (id: string) => void;
}

export function MobileCampList({ rows, onPick }: Props) {
  const { coords } = useUserLocation();
  return (
    <ul>
      {rows.map((r) => {
        const km =
          coords && typeof r.lat === "number" && typeof r.lon === "number"
            ? haversineKm(coords.lat, coords.lon, r.lat, r.lon)
            : null;
        return (
          <li
            key={r.id}
            className="px-4 py-4 border-b active:bg-stone-50 cursor-pointer"
            style={{ borderColor: "rgba(26,26,23,0.06)" }}
            onClick={() => onPick(r.id)}
          >
            <div className="flex items-baseline justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="font-semibold truncate">{r.name}</div>
                <div className="text-xs text-stone-500 mt-0.5">
                  {r.sido} · {r.sigungu}
                </div>
              </div>
              {km != null && (
                <div className="text-sm text-stone-600 num">
                  {formatKm(km)}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
