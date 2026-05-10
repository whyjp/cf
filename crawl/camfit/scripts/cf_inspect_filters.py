"""Trigger filter combinations on /search to discover camp-list endpoints
beyond /v1/collections (which is a curated set of ~89 camps).

Strategy:
    1. Click each theme chip — see what XHR is fired.
    2. Click each region (sido) chip — observe paginated calls.
    3. Click search keywords like "계곡" / "키즈" — observe.
    4. Capture all unique camfit XHR URLs and dedupe.
"""
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from cloakbrowser import launch


HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
OUT = DATA / "filter_inspect"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> int:
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    seen_urls: dict[str, int] = defaultdict(int)
    saved = 0
    interesting: list[tuple[str, int, str]] = []  # (label, status, url)

    def on_response(resp):
        nonlocal saved
        try:
            url = resp.url
            if "camfit.co.kr" not in url:
                return
            if not resp.ok:
                return
            ct = (resp.headers.get("content-type") or "")
            if "json" not in ct:
                return
            seen_urls[url] += 1
            # Save unique non-trivial JSONs (likely API endpoints)
            if seen_urls[url] == 1:
                body = resp.body()
                if len(body) > 500:
                    saved += 1
                    (OUT / f"f_{saved:03d}.json").write_bytes(body)
                    (OUT / f"f_{saved:03d}.url.txt").write_text(url, encoding="utf-8")
        except Exception:
            pass

    page.on("response", on_response)

    print("[probe] /search")
    page.goto("https://camfit.co.kr/search", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)

    # Click various theme/category chips
    candidates = [
        # Theme chips
        ('text=찾아오는체험', "theme:체험"),
        ('text=뷰 맛집', "theme:뷰"),
        ('text=#인별맛집', "theme:인별맛집"),
        ('text=대형견과함께', "theme:대형견"),
        ('text=인기급상승', "theme:인기"),
        ('text=파인스테이', "theme:파인"),
        # Filter chips
        ('text=계곡', "filter:계곡"),
        ('text=키즈', "filter:키즈"),
        ('text=오토캠핑', "filter:오토캠핑"),
        ('text=글램핑', "filter:글램핑"),
    ]
    for sel, label in candidates:
        try:
            print(f"  click {label}")
            page.click(sel, timeout=2500)
            page.wait_for_load_state("networkidle", timeout=8000)
            time.sleep(1.5)
            # Scroll to trigger pagination
            for _ in range(8):
                page.mouse.wheel(0, 1500)
                time.sleep(0.3)
            page.wait_for_load_state("networkidle", timeout=5000)
            # Go back to search base
            page.goto("https://camfit.co.kr/search", wait_until="domcontentloaded", timeout=30000)
            time.sleep(1)
        except Exception as e:
            print(f"    skip ({type(e).__name__})")
            continue

    b.close()

    print(f"\n[done] unique URLs: {len(seen_urls)}  saved: {saved}")
    print("\nUnique camfit JSON endpoints (deduped, sorted by hits):")
    for u, n in sorted(seen_urls.items(), key=lambda x: -x[1]):
        if "api.camfit.co.kr" in u:
            short = u.replace("https://api.camfit.co.kr", "")
            print(f"  {n:>3d}  {short[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
