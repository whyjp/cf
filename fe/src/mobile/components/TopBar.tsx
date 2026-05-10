import { useEffect, useRef, useState } from "react";
import { DesktopToggle } from "./DesktopToggle";

/**
 * TopBar — 56dp h-14 헤더, menu / title / search.
 *
 * C3: search 버튼 onClick 활성화 — onSearch prop 받아서 MobileShell 의
 * MobileSearchOverlay open state 를 토글.
 * C5: menu (≡) 버튼이 dropdown 토글 → DesktopToggle ("데스크톱으로") 노출.
 *     dropdown outside click + esc 로 닫힘. 추가 메뉴 항목은 후속 sprint
 *     에서 본 dropdown 안에 누적.
 */
interface Props {
  onSearch?: () => void;
}

export function TopBar({ onSearch }: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (!menuRef.current) return;
      if (!menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  return (
    <header
      className="h-14 px-4 flex items-center justify-between border-b flex-shrink-0 relative"
      style={{ borderColor: "rgba(26,26,23,0.12)", background: "var(--paper)" }}
    >
      <div ref={menuRef} className="relative">
        <button
          aria-label="menu"
          aria-haspopup="menu"
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)}
          className="text-xl leading-none w-10 h-10 flex items-center justify-center -ml-2"
        >
          ≡
        </button>
        {menuOpen && (
          <div
            role="menu"
            data-testid="mobile-menu"
            className="absolute top-12 left-0 z-30 min-w-[180px] rounded-lg border shadow-lg p-2 flex flex-col gap-1"
            style={{
              background: "var(--paper)",
              borderColor: "rgba(26,26,23,0.18)",
            }}
          >
            <DesktopToggle className="w-full text-left px-3 py-2 rounded text-sm font-medium hover:bg-stone-100" />
          </div>
        )}
      </div>
      <h1 className="display text-base font-bold">camfit</h1>
      <button
        aria-label="search"
        onClick={onSearch}
        className="text-xl leading-none w-10 h-10 flex items-center justify-center -mr-2"
      >
        🔍
      </button>
    </header>
  );
}
