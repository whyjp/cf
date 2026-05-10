/**
 * TopBar — 56dp h-14 헤더, menu / title / search.
 *
 * C1 placeholder: 버튼 onClick 미연결. C3 가 search 다이얼로그를,
 * C4 가 menu/필터 FAB 흐름을 부착.
 */
export function TopBar() {
  return (
    <header
      className="h-14 px-4 flex items-center justify-between border-b flex-shrink-0"
      style={{ borderColor: "rgba(26,26,23,0.12)", background: "var(--paper)" }}
    >
      <button aria-label="menu" className="text-xl leading-none w-10 h-10 flex items-center justify-center -ml-2">
        ≡
      </button>
      <h1 className="display text-base font-bold">camfit</h1>
      <button aria-label="search" className="text-xl leading-none w-10 h-10 flex items-center justify-center -mr-2">
        🔍
      </button>
    </header>
  );
}
