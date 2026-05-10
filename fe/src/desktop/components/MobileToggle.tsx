import { useEffect, useState } from "react";

/**
 * MobileToggle — desktop bundle 의 헤더에 노출되는 "모바일 보기" 버튼.
 *
 * matchMedia("(max-width: 640px)") 가 매칭될 때만 노출 — wide viewport 에서는
 * 굳이 모바일 옵션을 보여줄 이유 없음. 좁은 viewport 에서 desktop 으로
 * 잘못 들어온 사용자를 위한 fallback 진입 (e.g. UA 가 데스크톱이지만 작은
 * 창, 또는 prefer_desktop=1 이 설정된 모바일).
 *
 * 클릭 시:
 *   1) localStorage.prefer_mobile = "1"
 *   2) cookie prefer_mobile=1 (path=/, max-age=1년)
 *   3) prefer_desktop 정리
 *   4) location.assign("/m.html")
 */
const ONE_YEAR_S = 60 * 60 * 24 * 365;
const NARROW_QUERY = "(max-width: 640px)";

function setCookie(name: string, value: string, maxAgeSeconds: number) {
  document.cookie = `${name}=${value}; path=/; max-age=${maxAgeSeconds}; samesite=lax`;
}

function clearCookie(name: string) {
  document.cookie = `${name}=; path=/; max-age=0; samesite=lax`;
}

export function MobileToggle() {
  const [narrow, setNarrow] = useState(() => {
    if (typeof window === "undefined" || !window.matchMedia) return false;
    return window.matchMedia(NARROW_QUERY).matches;
  });

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mql = window.matchMedia(NARROW_QUERY);
    const onChange = (e: MediaQueryListEvent) => setNarrow(e.matches);
    // Safari < 14 호환: addListener fallback
    if (mql.addEventListener) mql.addEventListener("change", onChange);
    else mql.addListener(onChange);
    return () => {
      if (mql.removeEventListener) mql.removeEventListener("change", onChange);
      else mql.removeListener(onChange);
    };
  }, []);

  if (!narrow) return null;

  return (
    <button
      type="button"
      className="px-2 py-1 rounded text-xs font-medium border hairline"
      style={{ background: "var(--paper)" }}
      onClick={() => {
        try {
          window.localStorage.setItem("prefer_mobile", "1");
          window.localStorage.removeItem("prefer_desktop");
          window.sessionStorage.removeItem("cf_redirect_count");
        } catch {
          /* privacy mode — cookie path 으로 fallback */
        }
        setCookie("prefer_mobile", "1", ONE_YEAR_S);
        clearCookie("prefer_desktop");
        window.location.assign("/m.html");
      }}
    >
      📱 모바일 보기
    </button>
  );
}
