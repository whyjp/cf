import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./styles.css";

/**
 * C5: client-side viewport guard.
 *
 * Server-side root_redirect 는 UA + cookie 기반 — UA 가 desktop 인데 viewport
 * 가 좁은 (e.g. dev tools narrow window, foldable) 경우엔 잡지 못한다. 이 가
 * 드는 narrow viewport && !prefer_desktop 일 때 즉시 /m.html 로 보낸다.
 *
 * Loop guard: sessionStorage 의 cf_redirect_count 가 max(=3) 이상이면 더
 * redirect 안 함 — iOS Safari 의 privacy mode 가 cookie 를 드롭해 무한 redir-
 * ect 가 생기는 경우 방지. throw 로 React mount 자체를 차단해야 redirect
 * 직전에 React tree 가 먼저 그려지지 않는다.
 */
const NARROW_QUERY = "(max-width: 640px)";
const MAX_REDIRECTS = 3;

function preferDesktop(): boolean {
  try {
    if (window.localStorage.getItem("prefer_desktop") === "1") return true;
  } catch {
    /* privacy mode */
  }
  return document.cookie
    .split(";")
    .some((c) => c.trim() === "prefer_desktop=1");
}

function tryRedirectToMobile() {
  if (typeof window === "undefined" || !window.matchMedia) return;
  if (!window.matchMedia(NARROW_QUERY).matches) return;
  if (preferDesktop()) return;

  let count = 0;
  try {
    count = Number(window.sessionStorage.getItem("cf_redirect_count") ?? "0") || 0;
  } catch {
    /* ignore */
  }
  if (count >= MAX_REDIRECTS) return;
  try {
    window.sessionStorage.setItem("cf_redirect_count", String(count + 1));
  } catch {
    /* ignore */
  }
  window.location.replace("/m.html");
  // throw 로 React mount 차단 — redirect 직전 깜빡임 방지.
  throw new Error("redirected to /m.html");
}

tryRedirectToMobile();

const root = document.getElementById("root");
if (!root) throw new Error("#root not found");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// esc 단축키 — 원본 fe/index.legacy.html line ~1786. App also wires its
// own listener to clear pickedId; this CustomEvent kept for any future
// independent panel that wants to subscribe.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    window.dispatchEvent(new CustomEvent("camfit:close-detail"));
  }
});
