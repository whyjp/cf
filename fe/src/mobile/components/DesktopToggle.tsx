/**
 * DesktopToggle — mobile bundle 에서 노출되는 "데스크톱으로" 버튼.
 *
 * 클릭 시:
 *   1) localStorage.prefer_desktop = "1"
 *   2) document.cookie prefer_desktop=1 (path=/, max-age=1년)
 *   3) prefer_mobile 쿠키/스토리지 정리
 *   4) location.assign("/") — BFF 의 root_redirect 가 cookie 보고 desktop 서빙
 *
 * 쿠키 + localStorage 양쪽: cookie 는 서버측 라우팅용, localStorage 는
 * 클라이언트측 가드 (desktop main.tsx) 가 좁은 viewport 에서도 desktop
 * 유지할지 판단할 때 읽음.
 */
interface Props {
  className?: string;
  label?: string;
}

const ONE_YEAR_S = 60 * 60 * 24 * 365;

function setCookie(name: string, value: string, maxAgeSeconds: number) {
  document.cookie = `${name}=${value}; path=/; max-age=${maxAgeSeconds}; samesite=lax`;
}

function clearCookie(name: string) {
  document.cookie = `${name}=; path=/; max-age=0; samesite=lax`;
}

export function DesktopToggle({ className, label = "데스크톱으로" }: Props) {
  return (
    <button
      type="button"
      className={
        className ??
        "px-3 py-2 rounded-lg border text-sm font-medium hairline"
      }
      style={{ background: "var(--paper)" }}
      onClick={() => {
        try {
          window.localStorage.setItem("prefer_desktop", "1");
          window.localStorage.removeItem("prefer_mobile");
        } catch {
          // privacy mode 등 — cookie 만으로도 동작
        }
        setCookie("prefer_desktop", "1", ONE_YEAR_S);
        clearCookie("prefer_mobile");
        // sessionStorage 의 redirect counter 도 리셋해서 desktop 진입 직후
        // client-side guard 가 즉시 다시 모바일로 튕기지 않도록.
        try {
          window.sessionStorage.removeItem("cf_redirect_count");
        } catch {
          /* ignore */
        }
        window.location.assign("/");
      }}
    >
      {label}
    </button>
  );
}
