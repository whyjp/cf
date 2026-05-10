import { useCallback, useRef, useState } from "react";

/**
 * BottomSheet 3-snap state machine — pointer-events 기반, RN/Lib 의존성 0.
 *
 * 스냅 정의:
 *   peek = 120dp (헤더 + 카드 1줄 살짝)
 *   half = window.innerHeight 의 50% (dvh-equivalent)
 *   full = innerHeight - 56 (TopBar 높이 빼기)
 *
 * 드래그 결정 로직 (onPointerUp):
 *   |velocity| > 0.5 px/ms → flick 방향으로 한 칸 점프 (peek↔half↔full)
 *   |velocity| ≤ 0.5 px/ms → 가장 가까운 스냅으로 흡착
 *
 * pointer events 를 쓰는 이유: touch + mouse + pen 통합. iOS Safari 의 touch
 * 만 들어오면 데스크탑 dev tools 에뮬레이션이나 trackpad 기기에서 깨짐.
 * setPointerCapture 로 손가락이 핸들 영역을 벗어나도 추적 유지.
 */

export type Snap = "peek" | "half" | "full";

export const SNAP_HEIGHTS: Record<Snap, (vh: number) => number> = {
  peek: () => 120,
  half: (vh) => Math.round(vh * 0.5),
  full: (vh) => vh - 56, // - TopBar 56dp
};

interface DragState {
  startY: number;
  startHeight: number;
  velocity: number; // px/ms, 위로 양수
  lastY: number;
  lastT: number;
}

/**
 * @returns
 *   snap            현재 스냅 위치
 *   setSnap         외부에서 강제 점프 (e.g. 검색 열 때 full 로)
 *   currentHeight   드래그 중이면 dragHeight, 아니면 SNAP_HEIGHTS[snap](vh)
 *   handleProps     {...handleProps} 로 BottomSheet 핸들 div 에 spread
 */
export function useBottomSheet(initial: Snap = "peek") {
  const [snap, setSnap] = useState<Snap>(initial);
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const stateRef = useRef<DragState | null>(null);

  const getVh = () => window.innerHeight;
  const currentHeight = dragHeight ?? SNAP_HEIGHTS[snap](getVh());

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      // 손가락이 핸들 영역을 벗어나도 move/up 이벤트 계속 받기.
      (e.target as Element).setPointerCapture(e.pointerId);
      stateRef.current = {
        startY: e.clientY,
        startHeight: SNAP_HEIGHTS[snap](getVh()),
        velocity: 0,
        lastY: e.clientY,
        lastT: performance.now(),
      };
    },
    [snap],
  );

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    const s = stateRef.current;
    if (!s) return;
    const dy = e.clientY - s.startY;
    // 시트는 위로 끌면 커지고, 아래로 끌면 작아진다 → startHeight - dy.
    // clamp [80, vh] — peek 보다 살짝 작은 80px 까지는 허용 (snap 결정 여유).
    const newH = Math.max(80, Math.min(getVh(), s.startHeight - dy));
    setDragHeight(newH);
    const t = performance.now();
    const dt = Math.max(1, t - s.lastT);
    // 마지막 sample 간 속도 — flick 감지용. 위로가 양수.
    s.velocity = (s.lastY - e.clientY) / dt;
    s.lastY = e.clientY;
    s.lastT = t;
  }, []);

  const onPointerUp = useCallback(() => {
    const s = stateRef.current;
    if (!s) return;
    stateRef.current = null;
    const h = dragHeight ?? SNAP_HEIGHTS[snap](getVh());
    const vh = getVh();
    // 속도 임계 — |v| > 0.5 px/ms 면 flick 으로 보고 방향으로 한 칸.
    if (s.velocity > 0.5) {
      setSnap(snap === "peek" ? "half" : "full");
    } else if (s.velocity < -0.5) {
      setSnap(snap === "full" ? "half" : "peek");
    } else {
      // 거리로 결정 — 가장 가까운 스냅으로 흡착.
      const peekH = SNAP_HEIGHTS.peek(vh);
      const halfH = SNAP_HEIGHTS.half(vh);
      const fullH = SNAP_HEIGHTS.full(vh);
      const dPeek = Math.abs(h - peekH);
      const dHalf = Math.abs(h - halfH);
      const dFull = Math.abs(h - fullH);
      if (dPeek <= dHalf && dPeek <= dFull) setSnap("peek");
      else if (dHalf <= dFull) setSnap("half");
      else setSnap("full");
    }
    setDragHeight(null);
  }, [dragHeight, snap]);

  return {
    snap,
    setSnap,
    currentHeight,
    handleProps: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: onPointerUp,
    },
  };
}
