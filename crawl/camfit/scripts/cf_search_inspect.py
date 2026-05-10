"""Trigger an actual search action on /search → reveal camp list endpoint."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from cloakbrowser import launch


HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data" / "search_inspect"
DATA.mkdir(parents=True, exist_ok=True)


def main() -> int:
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    log: list[dict] = []
    saved = 0

    def on_response(resp):
        nonlocal saved
        try:
            if resp.request.resource_type in {"xhr", "fetch"} and "camfit.co.kr" in resp.url:
                ct = (resp.headers.get("content-type") or "")
                if "json" in ct and resp.ok:
                    body = resp.body()
                    if len(body) > 200:
                        saved += 1
                        idx = f"{saved:03d}"
                        (DATA / f"r_{idx}.json").write_bytes(body)
                        (DATA / f"r_{idx}.url.txt").write_text(
                            f"{resp.request.method} {resp.url}", encoding="utf-8"
                        )
        except Exception:
            pass

    def on_request(req):
        if req.resource_type in {"xhr", "fetch"} and "camfit.co.kr" in req.url:
            log.append({"method": req.method, "url": req.url})

    page.on("request", on_request)
    page.on("response", on_response)

    print("[search] /search → wait + scroll + filter clicks")
    page.goto("https://camfit.co.kr/search", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(3)

    # Try opening filter panel and selecting a region
    try:
        # Click any 지역 button
        page.click("text=지역", timeout=3000)
        time.sleep(1.5)
    except Exception:
        pass

    # Scroll multiple times to trigger more list-load XHRs
    for _ in range(15):
        page.mouse.wheel(0, 1500)
        time.sleep(0.4)
    page.wait_for_load_state("networkidle", timeout=8000)

    # Try direct text input search
    try:
        boxes = page.locator("input[type=text], input[type=search]")
        cnt = boxes.count()
        if cnt:
            boxes.first.click()
            time.sleep(0.5)
            page.keyboard.type("계곡", delay=80)
            time.sleep(2)
            page.keyboard.press("Enter")
            time.sleep(3)
            for _ in range(10):
                page.mouse.wheel(0, 1500)
                time.sleep(0.4)
    except Exception as e:
        print("[search] text-input flow:", type(e).__name__, e)

    b.close()

    print(f"\n[search] camfit XHR/fetch: {len(log)}")
    for it in log:
        print(f"  {it['method']:5s} {it['url']}")
    print(f"[search] JSON bodies saved: {saved} (in data/search_inspect/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
