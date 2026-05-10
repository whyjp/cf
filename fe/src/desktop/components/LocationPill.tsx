import type { UserCoords, UserLocStatus } from "../../shared/types";

/**
 * Header-corner indicator + retry button. Plain text per status, all
 * inline so it stays a single sibling among Stat / SearchBox / toggle.
 *
 * Origin: fe/index.legacy.html:395-425.
 */
export interface LocationPillProps {
  userLoc: {
    coords: UserCoords | null;
    status: UserLocStatus;
    refresh: () => void;
  };
}

export function LocationPill({ userLoc }: LocationPillProps) {
  const { coords, status, refresh } = userLoc || {};
  const label = (() => {
    switch (status) {
      case "ok":
        return `🧭 내 위치 사용 중 · ${coords!.lat.toFixed(2)},${coords!.lon.toFixed(2)}`;
      case "asking":
        return "🧭 위치 권한 요청 중…";
      case "denied":
        return "🧭 위치 차단됨 — 거리 정렬 비활성";
      case "error":
        return "🧭 위치 가져오기 실패";
      case "unsupported":
        return "🧭 브라우저 위치 미지원";
      default:
        return "🧭 위치 확인 중…";
    }
  })();
  const isFinal =
    status === "ok" || status === "denied" || status === "error" || status === "unsupported";
  return (
    <button
      onClick={refresh}
      title="클릭하여 위치 다시 가져오기"
      className="text-[10.5px] num"
      style={{
        background: status === "ok" ? "rgba(37,99,235,0.08)" : "rgba(26,26,23,0.05)",
        color: status === "ok" ? "#2563eb" : "rgba(26,26,23,0.6)",
        border: `1px solid ${status === "ok" ? "rgba(37,99,235,0.3)" : "rgba(26,26,23,0.13)"}`,
        borderRadius: "999px",
        padding: "3px 10px",
        cursor: isFinal ? "pointer" : "default",
      }}
    >
      {label}
    </button>
  );
}
