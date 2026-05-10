"""For each camp in data/camps_dedup.json, navigate to /camp/{id} and use
page.expect_response with a per-URL predicate to capture /v1/camps/{id} +
/v1/camp/{id}/reviews deterministically. Saves to:
    data/details/<id>.json
    data/reviews/<id>.json

Usage:
    python scripts/cf_pull_details.py            # all
    python scripts/cf_pull_details.py 5          # first 5 only
    python scripts/cf_pull_details.py --missing  # only fetch missing ones
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
DETAILS = DATA / "details"
REVIEWS = DATA / "reviews"
DETAILS.mkdir(parents=True, exist_ok=True)
REVIEWS.mkdir(parents=True, exist_ok=True)


# Path patterns we care about (per-camp).
_DETAIL_RE = re.compile(r"/v1/camps/[a-f0-9]{24}(?:\?|$)")
_REVIEWS_RE = re.compile(r"/v1/camp/[a-f0-9]{24}/reviews")


def _is_detail(url: str, cid: str) -> bool:
    if "/v1/camps/zones/" in url:
        return False
    if f"/v1/camps/{cid}" not in url:
        return False
    # exclude any sub-path like /v1/camps/{id}/reviews-summary etc.
    tail = url.split(f"/v1/camps/{cid}", 1)[1]
    return tail == "" or tail.startswith("?")


def _is_reviews(url: str, cid: str) -> bool:
    return f"/v1/camp/{cid}/reviews" in url and "page=1" in url


def main() -> int:
    flat = json.loads((DATA / "camps_dedup.json").read_text(encoding="utf-8"))
    args = sys.argv[1:]
    only_missing = "--missing" in args

    if only_missing:
        # Either detail OR reviews missing
        targets = []
        for c in flat:
            cid = c.get("id") or c.get("_id")
            if not (DETAILS / f"{cid}.json").exists() or not (REVIEWS / f"{cid}.json").exists():
                targets.append(cid)
        print(f"[detail-fetch] missing-only mode (detail OR reviews): {len(targets)} camps to fetch")
    else:
        nums = [int(a) for a in args if a.isdigit()]
        limit = nums[0] if nums else len(flat)
        targets = [(c.get("id") or c.get("_id")) for c in flat[:limit]]
        print(f"[detail-fetch] {len(targets)} camps to fetch")

    if not targets:
        print("[done] nothing to do")
        return 0

    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    print("[bootstrap] / ...")
    page.goto("https://camfit.co.kr/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(2)

    success = 0
    failures: list[str] = []

    for i, cid in enumerate(targets, 1):
        d_path = DETAILS / f"{cid}.json"
        r_path = REVIEWS / f"{cid}.json"
        if d_path.exists() and r_path.exists():
            success += 1
            print(f"  [{i:3d}/{len(targets)}]  {cid}  cached")
            continue

        need_detail = not d_path.exists()
        need_reviews = not r_path.exists()

        if need_detail:
            try:
                with page.expect_response(
                    lambda r, _cid=cid: _is_detail(r.url, _cid) and r.status == 200,
                    timeout=25000,
                ) as detail_ev:
                    page.goto(f"https://camfit.co.kr/camp/{cid}", wait_until="domcontentloaded", timeout=45000)
                d_path.write_bytes(detail_ev.value.body())
            except Exception as e:
                failures.append(f"{cid}: detail wait: {e}")
                print(f"  [{i:3d}/{len(targets)}]  {cid}  no detail")
                continue
        else:
            # already have detail — still need to navigate so reviews XHR fires
            page.goto(f"https://camfit.co.kr/camp/{cid}", wait_until="domcontentloaded", timeout=45000)

        if need_reviews:
            try:
                with page.expect_response(
                    lambda r, _cid=cid: _is_reviews(r.url, _cid) and r.status == 200,
                    timeout=25000,
                ) as rev_ev:
                    # Aggressive scrolls to trigger reviews section render
                    for _ in range(6):
                        page.mouse.wheel(0, 1800)
                        time.sleep(0.5)
                    # Try clicking review tab if visible
                    for sel in ('text=리뷰', 'text=후기', '[data-testid*="review"]'):
                        try:
                            page.click(sel, timeout=1500)
                            break
                        except Exception:
                            continue
                r_path.write_bytes(rev_ev.value.body())
                success += 1
                print(f"  [{i:3d}/{len(targets)}]  {cid}  ok (d+r)")
            except Exception:
                # Detail saved but reviews timed out — perhaps 0 reviews on this camp.
                success += 1
                print(f"  [{i:3d}/{len(targets)}]  {cid}  ok (d only — no reviews)")
        else:
            success += 1
            print(f"  [{i:3d}/{len(targets)}]  {cid}  ok (filled)")

    b.close()
    print(f"[done] success {success}/{len(targets)}  fail {len(failures)}")
    if failures[:10]:
        print("  fail samples:")
        for f in failures[:10]:
            print(f"   - {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
