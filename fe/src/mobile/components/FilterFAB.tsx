/**
 * FilterFAB — 우하단 floating action button.
 *
 * 위치 정책:
 *   bottom-32 — BottomSheet peek 높이 (~ 88dp 시트 + 핸들) 위에 떠야
 *               시트 핸들과 겹치지 않는다. 시트가 half/full 로 올라오면
 *               시트가 FAB 위로 자연 덮인다 (z-50 > z-20). C5 에서
 *               시트 height 를 구독해서 동적 위치 조정 가능.
 *   right-4   — 우측 safe area + 16dp 그리드 정렬.
 *   z-20      — Map 마커(z-auto) 위, BottomSheet/DetailSheet (z-50) 아래.
 *
 * count 배지: > 0 일 때만 ember tone — "필터가 활성이다" 라는 강한 시각
 * 신호. 0 일 때는 라벨만으로 충분하므로 배지 자리에 빈 공간을 두지 않는다.
 *
 * Origin: docs/superpowers/plans/2026-05-10-fe-vite-and-mobile.md Task C4
 * Step 2.
 */
interface Props {
  count: number;
  onClick: () => void;
}

export function FilterFAB({ count, onClick }: Props) {
  return (
    <button
      onClick={onClick}
      className="fixed bottom-32 right-4 z-20 h-12 px-4 rounded-full shadow-lg flex items-center gap-2 font-medium"
      style={{ background: "var(--moss)", color: "#f7f4e8" }}
      aria-label="필터"
    >
      ✨ 필터
      {count > 0 && (
        <span
          className="ml-1 inline-flex items-center justify-center min-w-5 h-5 px-1.5 rounded-full text-xs num"
          style={{ background: "var(--ember)" }}
        >
          {count}
        </span>
      )}
    </button>
  );
}
