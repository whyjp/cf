"""Pull camfit collections by triggering infinite-scroll on /search and
intercepting each /v1/collections response that the page itself fires.

Avoids the 403 we get when calling api.camfit.co.kr directly (Cloudflare gates
api.* separately) by letting the SPA itself drive the requests.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from cloakbrowser import launch


HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)


def main() -> int:
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    captured_pages: dict[int, dict] = {}  # skip → payload
    raw_responses: list[bytes] = []

    def parse_skip(url: str) -> int:
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(url).query)
        try:
            return int(q.get("skip", ["-1"])[0])
        except ValueError:
            return -1

    def on_response(resp):
        try:
            url = resp.url
            if "api.camfit.co.kr/v1/collections" not in url:
                return
            if not resp.ok:
                return
            body = resp.body()
            if len(body) < 50:
                return
            try:
                payload = json.loads(body)
            except Exception:
                return
            skip = parse_skip(url)
            captured_pages[skip] = payload
            print(f"  [intercept] skip={skip:>4d}  collections={len(payload.get('data') or [])}  hasNext={payload.get('hasNext')}")
        except Exception as e:
            print(f"  [intercept-err] {e}")

    page.on("response", on_response)

    print("[search] navigating /search ...")
    page.goto("https://camfit.co.kr/search", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)

    # Aggressively scroll to trigger every paginated XHR.
    last_max = -1
    stagnant = 0
    for round_ in range(80):
        # Scroll to bottom; SPA typically observes intersection at the footer trigger.
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(0.5)
        page.mouse.wheel(0, 1500)
        time.sleep(0.4)
        page.mouse.wheel(0, 1500)
        time.sleep(0.7)
        cur = max(captured_pages.keys()) if captured_pages else -1
        if cur > last_max:
            stagnant = 0
            last_max = cur
        else:
            stagnant += 1
        if stagnant >= 6:
            print(f"  no new pages for 6 rounds — stop. last skip={last_max}")
            break

    # Final wait for any in-flight responses.
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    pages_sorted = [captured_pages[k] for k in sorted(captured_pages.keys())]
    all_collections: list[dict] = []
    for p in pages_sorted:
        all_collections.extend(p.get("data") or [])
    (DATA / "collections_full.json").write_text(
        json.dumps(all_collections, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[total] collections: {len(all_collections)}  (captured pages: {len(pages_sorted)})")

    seen: dict[str, dict] = {}
    for col in all_collections:
        col_name = col.get("name", "")
        for c in col.get("camps", []):
            cid = c.get("id") or c.get("_id")
            if not cid:
                continue
            if cid not in seen:
                c2 = dict(c)
                c2["_collections"] = []
                seen[cid] = c2
            if col_name and col_name not in seen[cid]["_collections"]:
                seen[cid]["_collections"].append(col_name)
    flat = list(seen.values())
    (DATA / "camps_dedup.json").write_text(
        json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[dedupe] unique camps: {len(flat)}")

    # Show city/region distribution + types
    from collections import Counter
    city_cnt = Counter(c.get("city") for c in flat if c.get("city"))
    type_cnt = Counter()
    for c in flat:
        for t in (c.get("type") or "").split(","):
            t = t.strip()
            if t:
                type_cnt[t] += 1
    print("[stats] sido top10:", dict(city_cnt.most_common(10)))
    print("[stats] type top10:", dict(type_cnt.most_common(10)))

    b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
