"""Visit one /camp/{id} page and capture every XHR/fetch JSON response.
Goal: identify the detail + reviews + photos endpoints.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from cloakbrowser import launch


HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
OUT = DATA / "cf_one_detail_inspect"
OUT.mkdir(parents=True, exist_ok=True)

CAMP_ID = sys.argv[1] if len(sys.argv) > 1 else None


def main() -> int:
    if not CAMP_ID:
        # pull first id from camps_dedup.json
        ids_path = DATA / "camps_dedup.json"
        if not ids_path.exists():
            print(f"error: {ids_path} missing — run cf_pull_via_scroll.py first")
            return 2
        flat = json.loads(ids_path.read_text(encoding="utf-8"))
        target = flat[0].get("id") or flat[0].get("_id")
    else:
        target = CAMP_ID
    print(f"[detail] target: /camp/{target}")

    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    saved = 0
    log: list[dict] = []

    def on_response(resp):
        nonlocal saved
        try:
            url = resp.url
            if resp.request.resource_type not in {"xhr", "fetch"}:
                return
            if "camfit.co.kr" not in url:
                return
            ct = (resp.headers.get("content-type") or "")
            if not resp.ok or "json" not in ct:
                return
            body = resp.body()
            if len(body) < 50:
                return
            saved += 1
            (OUT / f"d_{saved:03d}.json").write_bytes(body)
            (OUT / f"d_{saved:03d}.url.txt").write_text(
                f"{resp.request.method} {url}", encoding="utf-8"
            )
            log.append({"method": resp.request.method, "url": url, "size": len(body)})
        except Exception:
            pass

    page.on("response", on_response)

    # Bootstrap: home first → cookies/CF clearance.
    page.goto("https://camfit.co.kr/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)

    # Detail page.
    print("[detail] navigating ...")
    page.goto(f"https://camfit.co.kr/camp/{target}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=20000)
    time.sleep(3)

    # Scroll to trigger lazy-loaded sections (reviews, photos, similar camps)
    for _ in range(15):
        page.mouse.wheel(0, 1500)
        time.sleep(0.4)
    page.wait_for_load_state("networkidle", timeout=8000)

    # Try clicking "리뷰" or "후기" tab if present
    for sel in ('text=리뷰', 'text=후기', '[role="tab"]:has-text("리뷰")'):
        try:
            page.click(sel, timeout=2500)
            time.sleep(2)
            for _ in range(6):
                page.mouse.wheel(0, 1500)
                time.sleep(0.4)
            break
        except Exception:
            continue
    page.wait_for_load_state("networkidle", timeout=5000)

    b.close()
    print(f"[detail] saved {saved} JSON bodies → {OUT}")
    print()
    print("All endpoints touched (sorted by size):")
    for it in sorted(log, key=lambda x: -x["size"])[:40]:
        print(f"  {it['size']:>6d}  {it['method']:5s}  {it['url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
