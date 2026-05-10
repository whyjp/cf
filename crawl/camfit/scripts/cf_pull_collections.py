"""Pull all camfit collections via /v1/collections?key=search and discover the
camp-detail endpoint by visiting one /camp/{id} page. Output:
    data/collections_full.json   — concatenated raw collections
    data/camps_dedup.json        — deduped flat list of camp summaries
    data/cf_one_detail_inspect/  — detail-page XHR captures for the first camp
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from cloakbrowser import launch


HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
DETAIL_DIR = DATA / "cf_one_detail_inspect"
DETAIL_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "https://api.camfit.co.kr"


def main() -> int:
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    # First, hit the home page once to inherit cookies/session that pass CF.
    print("[bootstrap] homepage to acquire session ...")
    page.goto("https://camfit.co.kr/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)

    # Paginate via Playwright's APIRequestContext — inherits browser cookies + bypasses in-page CORS.
    api = ctx.request
    all_collections: list[dict] = []
    skip = 0
    limit = 20
    safety_max_pages = 200
    print(f"[paginate] /v1/collections?key=search skip+={limit}")
    for n in range(safety_max_pages):
        url = f"{API_BASE}/v1/collections?key=search&skip={skip}&limit={limit}"
        try:
            r = api.get(url, headers={
                "accept": "application/json",
                "referer": "https://camfit.co.kr/search",
                "origin": "https://camfit.co.kr",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            })
        except Exception as e:
            print(f"  page {n} error: {type(e).__name__}: {e}")
            break
        if not r.ok:
            print(f"  page {n}: HTTP {r.status}  {r.text()[:200]}")
            break
        try:
            payload = r.json()
        except Exception as e:
            print(f"  page {n} parse: {e}; body[:200]={r.text()[:200]}")
            break
        if not isinstance(payload, dict) or "data" not in payload:
            print(f"  page {n}: unexpected shape: {str(payload)[:200]}")
            break
        chunk = payload.get("data") or []
        all_collections.extend(chunk)
        has_next = bool(payload.get("hasNext"))
        print(f"  page {n}: skip={skip} → {len(chunk)} collections (total {len(all_collections)}) hasNext={has_next}")
        if not chunk or not has_next:
            break
        skip += limit
        time.sleep(0.4)

    (DATA / "collections_full.json").write_text(
        json.dumps(all_collections, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Flatten & dedupe.
    seen: dict[str, dict] = {}
    for col in all_collections:
        for c in col.get("camps", []):
            cid = c.get("id") or c.get("_id")
            if not cid or cid in seen:
                continue
            c["_collections"] = []
            seen[cid] = c
        for c in col.get("camps", []):
            cid = c.get("id") or c.get("_id")
            if cid in seen and col.get("name"):
                seen[cid]["_collections"].append(col["name"])
    flat = list(seen.values())
    (DATA / "camps_dedup.json").write_text(
        json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[dedupe] unique camps: {len(flat)}")

    # Probe detail endpoint by visiting one /camp/{id}.
    if flat:
        target = flat[0]
        target_id = target["id"]
        print(f"[detail] navigating /camp/{target_id} → capture XHR")
        captured = 0

        def on_response(resp):
            nonlocal captured
            try:
                if resp.request.resource_type in {"xhr", "fetch"} and "camfit.co.kr" in resp.url:
                    ct = resp.headers.get("content-type") or ""
                    if "json" in ct and resp.ok:
                        body = resp.body()
                        if len(body) > 100:
                            captured += 1
                            (DETAIL_DIR / f"d_{captured:03d}.json").write_bytes(body)
                            (DETAIL_DIR / f"d_{captured:03d}.url.txt").write_text(
                                f"{resp.request.method} {resp.url}", encoding="utf-8"
                            )
            except Exception:
                pass

        page.on("response", on_response)
        page.goto(f"https://camfit.co.kr/camp/{target_id}", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(3)
        for _ in range(8):
            page.mouse.wheel(0, 1500)
            time.sleep(0.3)
        page.wait_for_load_state("networkidle", timeout=8000)
        print(f"[detail] captures saved: {captured} → {DETAIL_DIR}")

    b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
