import type { ReactNode } from "react";
import { useBottomSheet, type Snap } from "../hooks/useBottomSheet";

/**
 * BottomSheet — 3단 스냅 (peek/half/full), pointer-events 핸들.
 *
 * 레이아웃:
 *   [핸들 영역 28dp — touch-action:none 으로 모든 터치 캡처]
 *   [body — overflow-y-auto, overscroll-contain (rubber-band 차단)]
 *
 * touch-action 정책:
 *   container = pan-x — 좌우 스와이프는 통과 (혹시 future swipe gesture).
 *                       세로 드래그는 핸들에서만 받기.
 *   handle    = none  — 모든 터치 제스처를 JS pointer events 에 위임.
 *                       이게 없으면 브라우저가 vertical pan 을 가로채서
 *                       핸들 드래그가 끊긴다.
 *
 * safe-area-inset-bottom: iOS 노치/홈인디케이터 영역 보호. viewport-fit=cover
 * 가 m.html meta 에 있으므로 env() 변수가 0 이상으로 채워진다.
 *
 * height transition 120ms — 스냅 결정 후 부드럽게 흡착. 드래그 중에는
 * dragHeight 가 매 move 마다 바뀌므로 사실상 transition 효과가 안 나오고
 * 손가락을 따라간다 (의도된 동작).
 */

interface Props {
  initial?: Snap;
  children: ReactNode;
}

export function BottomSheet({ initial, children }: Props) {
  const { currentHeight, handleProps } = useBottomSheet(initial);
  return (
    <div
      className="absolute bottom-0 left-0 right-0 rounded-t-2xl flex flex-col"
      style={{
        height: currentHeight,
        background: "var(--paper)",
        boxShadow: "0 -8px 24px -12px rgba(0,0,0,0.18)",
        paddingBottom: "env(safe-area-inset-bottom)",
        transition: "height 120ms ease-out",
        touchAction: "pan-x",
      }}
    >
      <div
        {...handleProps}
        className="flex justify-center items-center h-7 cursor-grab select-none"
        style={{ touchAction: "none" }}
        aria-label="sheet handle"
        role="separator"
      >
        <div className="w-9 h-1 rounded-full bg-stone-300" />
      </div>
      <div className="flex-1 overflow-y-auto overscroll-contain">{children}</div>
    </div>
  );
}
