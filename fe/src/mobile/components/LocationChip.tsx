import { useUserLocation } from "../../shared/hooks/useUserLocation";
import type { UserLocStatus } from "../../shared/types";

/**
 * LocationChip — 우상단 absolute pill, 위치 status 5종 표시.
 *
 * 탭 → useUserLocation.refresh() — 거부/오류 후 사용자가 다시 권한
 * 프롬프트를 띄우고 싶을 때를 위한 명시적 재요청 트리거.
 *
 * status 라벨은 UserLocStatus union 의 6 값 (idle/asking/ok/denied/
 * error/unsupported) 모두 매핑 — 빠지면 TS Record 가 에러.
 *
 * z-index 는 MobileShell 쪽 wrapper (top-3 right-3 z-10) 가 부여하므로
 * 본 컴포넌트는 위치/스택 컨텍스트에 무관심.
 */
const LABELS: Record<UserLocStatus, string> = {
  idle: "위치",
  asking: "위치 요청 중…",
  ok: "내 위치",
  denied: "위치 거부됨",
  error: "위치 오류",
  unsupported: "지원 안 함",
};

export function LocationChip() {
  const { status, refresh } = useUserLocation();
  return (
    <button
      onClick={refresh}
      className="px-3 py-1.5 rounded-full text-xs border shadow-sm"
      style={{
        borderColor: "rgba(26,26,23,0.18)",
        background: "var(--paper, white)",
      }}
    >
      📍 {LABELS[status]}
    </button>
  );
}
