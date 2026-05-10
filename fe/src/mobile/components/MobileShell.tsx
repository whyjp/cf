import { TopBar } from "./TopBar";

/**
 * MobileShell — h-dvh flex column.
 *
 * Layout:
 *   [TopBar 56dp]
 *   [main relative — 지도(절대) + BottomSheet(절대 bottom)]
 *
 * C1 placeholder: 지도 자리 + BottomSheet 자리. C2 에서 진짜 컴포넌트 부착.
 */
export function MobileShell() {
  return (
    <div className="h-dvh flex flex-col">
      <TopBar />
      <main className="flex-1 relative overflow-hidden">
        {/* 지도 자리 — C2 의 MobileMap 이 여기에 들어옴. */}
        <div
          className="absolute inset-0"
          style={{ background: "var(--paper-2)" }}
          aria-label="지도 placeholder"
        >
          <p className="text-center mt-20 text-stone-500 text-sm">
            지도 자리 (C2 에서 MobileMap)
          </p>
        </div>

        {/* BottomSheet 자리 — C2 의 BottomSheet 이 여기에 들어옴. */}
        <div
          className="absolute bottom-0 left-0 right-0 h-[120px] border-t"
          style={{
            borderColor: "rgba(26,26,23,0.12)",
            background: "var(--paper)",
          }}
          aria-label="BottomSheet placeholder"
        >
          <div className="mx-auto mt-2 w-9 h-1 rounded-full bg-stone-300" />
          <p className="text-center text-stone-500 mt-3 text-sm">
            BottomSheet 자리 (C2)
          </p>
        </div>
      </main>
    </div>
  );
}
