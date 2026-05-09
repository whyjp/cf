"""Discover camfit API endpoints exposed when clicking region / camp-type
filter chips on /search.

Strategy
--------
1. Launch CloakBrowser headless, navigate to /search.
2. Intercept ALL XHR/fetch JSON responses from camfit.co.kr.
3. Click each visible filter chip (region 지역, camp-type 캠핑유형, etc.)
   in sequence, scroll to trigger pagination, then navigate back.
4. Save every unique JSON response (> 200 bytes) to data/region_inspect/.
5. Print a summary of discovered API paths.

Stops after ~5 minutes wall-clock OR 30+ unique api.camfit.co.kr JSON URLs.
"""
from __future__ import annotations

import json
import sys
import time
import re
from collections import defaultdict
from pathlib import Path

from cloakbrowser import launch

HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
OUT = DATA / "region_inspect"
OUT.mkdir(parents=True, exist_ok=True)


WALL_LIMIT_S = 300  # 5 minutes max
TARGET_URLS = 30    # stop early if we see 30+ unique api endpoints


def main() -> int:
    t0 = time.time()
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    seen_urls: dict[str, int] = defaultdict(int)  # url → hit count
    saved = 0

    def on_response(resp):
        nonlocal saved
        try:
            url = resp.url
            if "camfit.co.kr" not in url:
                return
            if not resp.ok:
                return
            ct = resp.headers.get("content-type") or ""
            if "json" not in ct:
                return
            seen_urls[url] += 1
            if seen_urls[url] == 1:  # first time we see this URL
                try:
                    body = resp.body()
                    if len(body) < 200:
                        return
                    saved += 1
                    n = f"{saved:03d}"
                    (OUT / f"r_{n}.json").write_bytes(body)
                    (OUT / f"r_{n}.url.txt").write_text(url, encoding="utf-8")
                    path = url.replace("https://api.camfit.co.kr", "").split("?")[0]
                    print(f"  [capture #{saved}] {path}  ({len(body)} bytes)")
                except Exception as e:
                    print(f"  [capture-err] {e}")
        except Exception:
            pass

    page.on("response", on_response)

    def scroll_and_wait(rounds: int = 10):
        for _ in range(rounds):
            page.mouse.wheel(0, 1800)
            time.sleep(0.4)
        try:
            page.wait_for_load_state("networkidle", timeout=6000)
        except Exception:
            pass
        time.sleep(1)

    def go_search():
        page.goto("https://camfit.co.kr/search",
                  wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(2)

    # ── Initial load ──────────────────────────────────────────────────────────
    print("[A] initial /search load")
    go_search()
    scroll_and_wait(rounds=12)  # exhaust default collections pagination

    # ── Helper: click something, scroll, go back ───────────────────────────
    def probe(selector: str, label: str, timeout_ms: int = 3000) -> bool:
        if time.time() - t0 > WALL_LIMIT_S:
            return False
        try:
            page.click(selector, timeout=timeout_ms)
            print(f"  [click] {label}")
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            time.sleep(1)
            scroll_and_wait(rounds=12)
            return True
        except Exception as e:
            print(f"  [skip]  {label}  ({type(e).__name__})")
            return False

    # ── Part B: type-filter chips ─────────────────────────────────────────────
    # These are the camp-type buttons (오토캠핑, 글램핑, 카라반, 펜션)
    type_labels = [
        ("text=오토캠핑", "type:autoCamping"),
        ("text=글램핑",   "type:glamping"),
        ("text=카라반",   "type:caravan"),
        ("text=펜션",     "type:pension"),
        ("text=캠핑",     "type:camping"),
    ]
    print("\n[B] type-filter chips")
    for sel, label in type_labels:
        if time.time() - t0 > WALL_LIMIT_S:
            break
        go_search()
        probe(sel, label)

    # ── Part C: region chips via top-level tab or chip ───────────────────────
    # Camfit search page usually shows a 지역 tab/button that opens a region picker
    region_selectors = [
        ("text=지역",     "region-tab"),
        ("text=전국",     "region:전국"),
    ]
    print("\n[C] region tab")
    for sel, label in region_selectors:
        if time.time() - t0 > WALL_LIMIT_S:
            break
        go_search()
        probe(sel, label, timeout_ms=4000)

    # ── Part D: individual sido chips (if visible without modal) ──────────────
    sidos = [
        "강원", "경기", "충남", "충북", "경북", "경남",
        "전남", "전북", "제주", "서울", "부산", "인천",
        "대구", "광주", "대전", "울산", "세종",
    ]
    print("\n[D] sido chips (direct text match)")
    for sido in sidos:
        if time.time() - t0 > WALL_LIMIT_S:
            break
        go_search()
        probed = probe(f"text={sido}", f"sido:{sido}", timeout_ms=3000)
        if probed:
            # also scroll more to capture all pages
            scroll_and_wait(rounds=20)

    # ── Part E: Try direct search URL patterns that may bypass chips ──────────
    # Some SPAs encode filters in the URL query-string / hash
    print("\n[E] URL param probes")
    url_probes = [
        ("https://camfit.co.kr/search?city=%EA%B0%95%EC%9B%90", "url:city=강원"),
        ("https://camfit.co.kr/search?type=autoCamping", "url:type=autoCamping"),
        ("https://camfit.co.kr/search?type=glamping", "url:type=glamping"),
        ("https://camfit.co.kr/search?region=%EA%B0%95%EC%9B%90", "url:region=강원"),
    ]
    for url, label in url_probes:
        if time.time() - t0 > WALL_LIMIT_S:
            break
        print(f"  [navigate] {label}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(1.5)
            scroll_and_wait(rounds=15)
        except Exception as e:
            print(f"    error: {e}")

    # ── Part F: campaigns endpoint ────────────────────────────────────────────
    print("\n[F] /campaigns URL probe")
    try:
        page.goto("https://camfit.co.kr/campaigns",
                  wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        time.sleep(1.5)
        scroll_and_wait(rounds=10)
    except Exception as e:
        print(f"    error: {e}")

    b.close()

    elapsed = time.time() - t0
    print(f"\n[done] elapsed={elapsed:.0f}s  unique URLs={len(seen_urls)}  saved={saved}")

    # Summary: unique api.camfit.co.kr paths
    api_paths: dict[str, list[str]] = defaultdict(list)
    for u in seen_urls:
        if "api.camfit.co.kr" in u:
            path = re.sub(r"/[a-f0-9]{24}", "/{id}", u.replace("https://api.camfit.co.kr", ""))
            path = path.split("?")[0]
            api_paths[path].append(u)

    print(f"\nDiscovered {len(api_paths)} unique api.camfit.co.kr path patterns:")
    for p in sorted(api_paths):
        count = len(api_paths[p])
        ex = api_paths[p][0]
        qs = ex.split("?")[1][:80] if "?" in ex else ""
        print(f"  {p}  [{count} variants]")
        if qs:
            print(f"      sample QS: {qs}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
