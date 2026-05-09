"""Expand camp list by walking each theme's /v1/themes/{id}/camps?skip=N&limit=50.

Strategy:
    1. Visit /search; capture /v1/themes list (theme IDs).
    2. For each theme, click its chip and intercept paginated /camps?skip=N&limit=10.
       Scroll until 0 new IDs arrive → next theme.
    3. Merge all camps into camps_dedup.json (preserving prior _collections list).

Note: this strategy stays inside the SPA so all XHRs come from the browser
context (Cloudflare-passing). No direct api.camfit.co.kr calls.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from cloakbrowser import launch


HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)
THEMES_DIR = DATA / "themes"
THEMES_DIR.mkdir(parents=True, exist_ok=True)


_THEME_LIST_RE = re.compile(r"/v1/themes\?skip=\d+&limit=\d+$")
_THEME_CAMPS_RE = re.compile(r"/v1/themes/([a-f0-9]{24})/camps\?skip=(\d+)&limit=(\d+)")


def main() -> int:
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    captured: dict[tuple[str, int], dict] = {}  # (theme_id, skip) → page payload
    themes_payloads: list[dict] = []

    def on_response(resp):
        try:
            url = resp.url
            if not resp.ok:
                return
            ct = (resp.headers.get("content-type") or "")
            if "json" not in ct:
                return
            if _THEME_LIST_RE.search(url):
                try:
                    themes_payloads.append(resp.json())
                except Exception:
                    pass
                return
            m = _THEME_CAMPS_RE.search(url)
            if m:
                tid = m.group(1)
                skip = int(m.group(2))
                try:
                    captured[(tid, skip)] = resp.json()
                    chunk_n = len((captured[(tid, skip)] or {}).get("data") or (captured[(tid, skip)] or {}).get("camps") or [])
                    print(f"  [intercept] theme {tid[:8]}.. skip={skip:>4d} → items={chunk_n}")
                except Exception:
                    pass
        except Exception:
            pass

    page.on("response", on_response)

    # Step A: visit /search to collect theme IDs (paginated)
    print("[A] /search -- collect theme IDs ...")
    page.goto("https://camfit.co.kr/search", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)
    # Try to scroll the themes carousel to trigger more pages
    for _ in range(20):
        page.mouse.wheel(0, 1500)
        time.sleep(0.4)
    page.wait_for_load_state("networkidle", timeout=8000)

    theme_ids: list[tuple[str, str]] = []  # (id, name)
    seen_t: set[str] = set()
    for tp in themes_payloads:
        for t in (tp.get("data") or []):
            tid = t.get("id") or t.get("_id")
            tname = t.get("name") or "?"
            if tid and tid not in seen_t:
                seen_t.add(tid)
                theme_ids.append((tid, tname))
    print(f"[A] discovered themes: {len(theme_ids)}")
    for tid, tname in theme_ids:
        print(f"    {tid}  {tname}")

    if not theme_ids:
        b.close()
        print("ERROR: no themes discovered — abort")
        return 1

    # Step B: for each theme, click its chip and exhaust pagination via scroll
    for ti, (tid, tname) in enumerate(theme_ids, 1):
        print(f"\n[B {ti}/{len(theme_ids)}] theme '{tname}' ({tid})")
        try:
            # Click theme chip via text
            page.goto("https://camfit.co.kr/search", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=8000)
            time.sleep(1.0)
            try:
                page.click(f"text={tname}", timeout=4000)
            except Exception:
                # Fallback: try chip via partial-match
                page.click(f"text={tname[:6]}", timeout=4000)
            page.wait_for_load_state("networkidle", timeout=8000)
            time.sleep(1)
            # Aggressively scroll to trigger pagination
            last_skip = -1
            stagnant = 0
            for _ in range(100):
                page.mouse.wheel(0, 2000)
                time.sleep(0.4)
                cur_skips = [s for (t, s) in captured.keys() if t == tid]
                cur_max = max(cur_skips) if cur_skips else -1
                if cur_max > last_skip:
                    last_skip = cur_max
                    stagnant = 0
                else:
                    stagnant += 1
                if stagnant >= 8:
                    break
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception as e:
            print(f"    failed: {type(e).__name__}: {e}")
            continue

    b.close()

    # Step C: aggregate
    by_theme: dict[str, list[dict]] = {}
    for (tid, skip), payload in sorted(captured.items()):
        data_arr = payload.get("data") or payload.get("camps") or []
        by_theme.setdefault(tid, []).extend(data_arr)

    seen: dict[str, dict] = {}
    # Preserve any previous _collections from camps_dedup.json
    prev_path = DATA / "camps_dedup.json"
    if prev_path.exists():
        try:
            for c in json.loads(prev_path.read_text(encoding="utf-8")):
                cid = c.get("id") or c.get("_id")
                if cid:
                    seen[cid] = c
        except Exception:
            pass

    theme_name_by_id = {tid: tn for tid, tn in theme_ids}
    new_count = 0
    for tid, items in by_theme.items():
        tname = theme_name_by_id.get(tid, tid)
        for c in items:
            cid = c.get("id") or c.get("_id")
            if not cid:
                continue
            if cid not in seen:
                c2 = dict(c)
                c2["_collections"] = []
                seen[cid] = c2
                new_count += 1
            tag = f"테마:{tname}"
            cols = seen[cid].setdefault("_collections", [])
            if tag not in cols:
                cols.append(tag)

    flat = list(seen.values())
    prev_path.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[done] themes processed: {len(by_theme)}/{len(theme_ids)}")
    print(f"      total unique camps: {len(flat)}  (+{new_count} new from themes)")
    for tid, items in by_theme.items():
        tname = theme_name_by_id.get(tid, tid)
        ids = {c.get("id") or c.get("_id") for c in items if c.get("id") or c.get("_id")}
        print(f"      [{tname:20s}] {len(items)} items / {len(ids)} unique ids")
    return 0


if __name__ == "__main__":
    sys.exit(main())
