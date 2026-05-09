"""Targeted browser-based camp discovery for approaches not tried by previous scripts.

This script uses CloakBrowser exclusively (no direct API calls) to avoid rate limits.
The SPA's own XHR calls are intercepted — they carry proper auth headers and bypass
the rate limit issues from Python requests.

Targeted approaches:
1. Fresh exhibition codes E360-E500 (beyond the E1-E359 range already tried)
2. Campaigns endpoint (/campaigns SPA page)
3. Sigungu-filtered search (city + specific sigungu combinations via UI clicks)
4. Keyword search sweep on /search (type into the search input)
5. Landing pages not yet visited

All results merged into data/camps_dedup.json.
"""
from __future__ import annotations

import json
import sys
import time
import re
from pathlib import Path

from cloakbrowser import launch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)

SITE_BASE = "https://camfit.co.kr"


def load_existing(path: Path) -> dict[str, dict]:
    existing: dict[str, dict] = {}
    if path.exists():
        for c in json.loads(path.read_text(encoding="utf-8")):
            cid = c.get("id") or c.get("_id")
            if cid:
                existing[cid] = c
    return existing


def save_existing(path: Path, existing: dict[str, dict]) -> None:
    flat = list(existing.values())
    path.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [save] {len(flat)} total camps")


def merge_camps(existing: dict[str, dict], camps: list[dict], tag: str) -> int:
    new_count = 0
    for c in camps:
        cid = c.get("id") or c.get("_id")
        if not cid:
            continue
        if cid not in existing:
            c2 = dict(c)
            c2.setdefault("_collections", [])
            existing[cid] = c2
            new_count += 1
        cols = existing[cid].setdefault("_collections", [])
        if tag not in cols:
            cols.append(tag)
    return new_count


def make_camp_interceptor(buckets: dict):
    """Create a response handler that captures all camp-list XHRs."""
    _EXHI_RE = re.compile(r"/v1/exhibitions/camp/([A-Z0-9]+)\?.*skip=(\d+)")
    _COLLECTION_CAMPS_RE = re.compile(r"/v1/collections/([a-f0-9]{24})/camps")
    _THEME_CAMPS_RE = re.compile(r"/v1/themes/([a-f0-9]{24})/camps")
    _CAMPAIGN_RE = re.compile(r"/v1/campaigns?")
    _LANDING_RE = re.compile(r"/v1/landings/([a-f0-9]{24})/camps")

    seen_urls: set[str] = set()

    def on_response(resp):
        try:
            if not resp.ok:
                return
            url = resp.url
            if "camfit.co.kr" not in url:
                return
            ct = resp.headers.get("content-type") or ""
            if "json" not in ct:
                return
            if url in seen_urls:
                return
            seen_urls.add(url)

            body = resp.body()
            if not body or len(body) < 20:
                return
            payload = json.loads(body)

            def get_items(p):
                if isinstance(p, list):
                    return p
                if isinstance(p, dict):
                    return (p.get("data") or p.get("camps") or
                            p.get("results") or [])
                return []

            items = get_items(payload)

            m = _EXHI_RE.search(url)
            if m:
                code, skip = m.group(1), int(m.group(2))
                if items:
                    buckets.setdefault("exhibitions", {}).setdefault(code, []).extend(items)
                    print(f"    [exh] {code} skip={skip} -> {len(items)} camps")
                return

            m = _COLLECTION_CAMPS_RE.search(url)
            if m:
                cid = m.group(1)
                if items:
                    buckets.setdefault("collections", {}).setdefault(cid, []).extend(items)
                return

            m = _THEME_CAMPS_RE.search(url)
            if m:
                tid = m.group(1)
                if items:
                    buckets.setdefault("themes", {}).setdefault(tid, []).extend(items)
                return

            m = _LANDING_RE.search(url)
            if m:
                lid = m.group(1)
                if items:
                    buckets.setdefault("landings", {}).setdefault(lid, []).extend(items)
                return

            if _CAMPAIGN_RE.search(url):
                if items:
                    buckets.setdefault("campaigns", []).extend(items)
                    print(f"    [campaign] {url} -> {len(items)} items")
                return

        except Exception:
            pass

    return on_response


def scroll_exhaust(page, marker_fn, max_rounds: int = 80, stagnant_limit: int = 10):
    last = marker_fn()
    stagnant = 0
    for _ in range(max_rounds):
        page.mouse.wheel(0, 2000)
        time.sleep(0.4)
        cur = marker_fn()
        if cur != last:
            last = cur
            stagnant = 0
        else:
            stagnant += 1
            if stagnant >= stagnant_limit:
                break


def wait_idle(page, timeout: int = 8000):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except Exception:
        pass


def boot(page, url: str = f"{SITE_BASE}/search"):
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    wait_idle(page)
    time.sleep(1.5)


# ── Phase 1: Fresh exhibition codes E360-E500 ─────────────────────────────────

def phase_fresh_exhibitions(page, buckets: dict, existing: dict) -> int:
    print("\n[Phase A] Fresh exhibition codes E360-E500 ...")
    total_new = 0
    empty_streak = 0

    # Boot once
    boot(page)

    for n in range(360, 501):
        code = f"E{n}"
        prev_count = len(buckets.get("exhibitions", {}).get(code, []))
        try:
            page.goto(f"{SITE_BASE}/exhibition/{code}",
                      wait_until="domcontentloaded", timeout=20000)
            wait_idle(page, timeout=6000)
            time.sleep(0.8)

            def exh_marker():
                return len(buckets.get("exhibitions", {}).get(code, []))

            # Quick check: did we get any items?
            time.sleep(0.5)
            got = len(buckets.get("exhibitions", {}).get(code, []))
            if got > prev_count:
                print(f"  {code}: has data ({got}) -> scrolling")
                empty_streak = 0
                scroll_exhaust(page, exh_marker, max_rounds=80, stagnant_limit=10)
                wait_idle(page)
                items = buckets.get("exhibitions", {}).get(code, [])
                new_n = merge_camps(existing, items, f"전시:{code}")
                total_new += new_n
                if new_n > 0:
                    print(f"  {code}: +{new_n} NEW camps!")
            else:
                empty_streak += 1
                print(f"  {code}: empty (streak={empty_streak})")
                if empty_streak >= 15:
                    print(f"  {empty_streak} empty streak -> stopping E360+ probe")
                    break

        except Exception as e:
            print(f"  {code}: error {type(e).__name__}")
            empty_streak += 1
            if empty_streak >= 15:
                break

    print(f"  Total new from fresh exhibitions: {total_new}")
    return total_new


# ── Phase 2: Campaigns ────────────────────────────────────────────────────────

def phase_campaigns(page, buckets: dict, existing: dict) -> int:
    print("\n[Phase B] Campaigns endpoint ...")
    total_new = 0

    try:
        boot(page, f"{SITE_BASE}/campaigns")
        time.sleep(1)

        def camp_marker():
            return len(buckets.get("campaigns", []))

        scroll_exhaust(page, camp_marker, max_rounds=40, stagnant_limit=8)
        wait_idle(page)

        # Also try navigating through campaign items
        campaign_items = buckets.get("campaigns", [])
        print(f"  Captured {len(campaign_items)} campaign items")

        # Check for exhibition or landing links in campaign items
        for ci in campaign_items:
            link = ci.get("link") or ci.get("url") or ""
            if "/exhibition/" in link:
                code = link.split("/exhibition/")[1].split("?")[0]
                print(f"  Campaign link -> exhibition {code}")
                try:
                    page.goto(f"{SITE_BASE}{link}", wait_until="domcontentloaded", timeout=20000)
                    wait_idle(page)
                    time.sleep(1)

                    def ex2_marker():
                        return len(buckets.get("exhibitions", {}).get(code, []))

                    scroll_exhaust(page, ex2_marker, max_rounds=60, stagnant_limit=8)
                    items = buckets.get("exhibitions", {}).get(code, [])
                    new_n = merge_camps(existing, items, f"전시:{code}")
                    if new_n > 0:
                        total_new += new_n
                        print(f"    -> +{new_n} new from campaign exh {code}")
                except Exception:
                    pass

        # Also try direct API for campaigns
        new_n = merge_camps(existing, campaign_items, "캠페인")
        total_new += new_n
        print(f"  Direct campaigns: +{new_n} new")

    except Exception as e:
        print(f"  Error: {type(e).__name__}: {e}")

    return total_new


# ── Phase 3: Sigungu exhaustion via browser UI ────────────────────────────────

def phase_sigungu(page, buckets: dict, existing: dict) -> int:
    """Click city+sigungu chip combos to trigger different exhibition XHRs."""
    print("\n[Phase C] Sigungu exhaustion via browser UI ...")

    sigungu_map = [
        # City, sigungu - prioritized by likely new camps
        ("강원", "평창군"), ("강원", "홍천군"), ("강원", "인제군"), ("강원", "양양군"),
        ("강원", "고성군"), ("강원", "속초시"), ("강원", "강릉시"), ("강원", "정선군"),
        ("강원", "춘천시"), ("강원", "원주시"), ("강원", "철원군"), ("강원", "화천군"),
        ("강원", "양구군"), ("강원", "영월군"), ("강원", "태백시"), ("강원", "삼척시"),
        ("경기", "가평군"), ("경기", "양평군"), ("경기", "포천시"), ("경기", "여주시"),
        ("경기", "연천군"), ("경기", "파주시"), ("경기", "광주시"),
        ("충남", "태안군"), ("충남", "보령시"), ("충남", "서산시"),
        ("충북", "제천시"), ("충북", "단양군"), ("충북", "충주시"),
        ("경북", "봉화군"), ("경북", "울진군"), ("경북", "청송군"), ("경북", "경주시"),
        ("경남", "남해군"), ("경남", "하동군"), ("경남", "함양군"), ("경남", "거창군"),
        ("전남", "여수시"), ("전남", "구례군"), ("전남", "완도군"),
        ("전북", "무주군"), ("전북", "진안군"),
        ("제주", "제주시"), ("제주", "서귀포시"),
    ]

    total_new = 0

    # Pre-count existing exhibitions captured
    def count_exh_items():
        return sum(len(v) for v in buckets.get("exhibitions", {}).values())

    for city, sigungu in sigungu_map:
        print(f"  [{city}/{sigungu}]", end=" ")
        prev = count_exh_items()
        try:
            boot(page)
            # Click city
            try:
                page.click(f"text={city}", timeout=3000)
                wait_idle(page, timeout=5000)
                time.sleep(0.5)
            except Exception:
                pass

            # Click sigungu
            try:
                page.click(f"text={sigungu}", timeout=3000)
                wait_idle(page, timeout=5000)
                time.sleep(0.5)
            except Exception:
                print(f"(couldn't click sigungu)", end=" ")

            def sg_marker():
                return count_exh_items()

            scroll_exhaust(page, sg_marker, max_rounds=60, stagnant_limit=8)
            wait_idle(page)

            # Merge all newly captured items
            all_new_items: list[dict] = []
            for code, items in buckets.get("exhibitions", {}).items():
                all_new_items.extend(items)

            # Dedup within batch
            seen_ids: set[str] = set()
            unique_new: list[dict] = []
            for c in all_new_items:
                cid = c.get("id") or c.get("_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    unique_new.append(c)

            new_n = merge_camps(existing, unique_new, f"시군구:{city}/{sigungu}")
            if new_n > 0:
                total_new += new_n
                print(f"-> +{new_n} NEW camps!")
            else:
                print("-> 0 new")

        except Exception as e:
            print(f"error: {type(e).__name__}")
        time.sleep(1.0)

    print(f"  Total new from sigungu: {total_new}")
    return total_new


# ── Phase 4: Keyword search sweep ────────────────────────────────────────────

def phase_keyword_search(page, buckets: dict, existing: dict) -> int:
    """Type keywords into the /search page's search input."""
    print("\n[Phase D] Keyword search sweep ...")

    keywords = [
        "캠핑", "글램핑", "오토캠핑", "카라반", "펜션",
        "계곡", "바다", "산", "호수", "강",
        "키즈", "반려", "프라이빗",
        "강원", "경기", "제주", "충남", "경남",
    ]

    total_new = 0

    def count_all_items():
        total = 0
        for v in buckets.get("exhibitions", {}).values():
            total += len(v)
        for v in buckets.get("collections", {}).values():
            total += len(v)
        return total

    for kw in keywords:
        print(f"  keyword: '{kw}'", end=" ")
        prev = count_all_items()
        try:
            boot(page)

            # Try to find and fill search input
            try:
                # Look for a search input/button
                page.click("input[type=search], input[placeholder*='검색'], input[placeholder*='캠핑']",
                            timeout=3000)
                page.keyboard.type(kw)
                page.keyboard.press("Enter")
            except Exception:
                try:
                    # Try clicking the search icon
                    page.click("[data-test*='search'], .search-input, [class*='search']",
                               timeout=2000)
                    page.keyboard.type(kw)
                    page.keyboard.press("Enter")
                except Exception:
                    # Navigate to search result URL
                    page.goto(
                        f"{SITE_BASE}/search?keyword={kw}",
                        wait_until="domcontentloaded", timeout=20000,
                    )

            wait_idle(page, timeout=6000)
            time.sleep(1)

            def kw_marker():
                return count_all_items()

            scroll_exhaust(page, kw_marker, max_rounds=50, stagnant_limit=8)
            wait_idle(page)

            # Merge
            all_items: list[dict] = []
            for v in buckets.get("exhibitions", {}).values():
                all_items.extend(v)
            for v in buckets.get("collections", {}).values():
                all_items.extend(v)

            seen_ids: set[str] = set()
            unique_items: list[dict] = []
            for c in all_items:
                cid = c.get("id") or c.get("_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    unique_items.append(c)

            new_n = merge_camps(existing, unique_items, f"검색:{kw}")
            if new_n > 0:
                total_new += new_n
                print(f"-> +{new_n} NEW camps!")
            else:
                print("-> 0 new")

        except Exception as e:
            print(f"error: {type(e).__name__}")
        time.sleep(1.5)

    print(f"  Total new from keyword search: {total_new}")
    return total_new


# ── Phase 5: Landing pages ────────────────────────────────────────────────────

def phase_landing_pages(page, buckets: dict, existing: dict) -> int:
    print("\n[Phase E] Landing pages ...")

    # All known landing IDs from mainBanners, curations, and filter items
    landing_ids = [
        "69dcb86e1174e8001d41e529",
        "69dcb6dc1174e8001d41e487",
        "69cea6b443bf19001d86e242",
        "69e9e55cadf3f3001d2c80c9",
        "69fc6279ce9755001d2cd43e",
        "69dca0d21d1c1a001d35986c",
        "688b1685b8bdce001daea359",
        "684833c2ea0a43001de569e0",
    ]

    total_new = 0

    for lid in landing_ids:
        print(f"  landing {lid[:12]}...", end=" ")
        try:
            page.goto(f"{SITE_BASE}/landing/{lid}",
                      wait_until="domcontentloaded", timeout=30000)
            wait_idle(page)
            time.sleep(1)

            def land_marker():
                return (len(buckets.get("landings", {}).get(lid, [])) +
                        sum(len(v) for v in buckets.get("exhibitions", {}).values()))

            scroll_exhaust(page, land_marker, max_rounds=60, stagnant_limit=8)
            wait_idle(page)

            items = buckets.get("landings", {}).get(lid, [])
            new_n = merge_camps(existing, items, f"랜딩:{lid[:8]}")
            total_new += new_n
            print(f"-> {len(items)} camps, +{new_n} new")

        except Exception as e:
            print(f"error: {type(e).__name__}")
        time.sleep(1.5)

    return total_new


# ── Phase 6: Type-filtered search ────────────────────────────────────────────

def phase_type_search(page, buckets: dict, existing: dict) -> int:
    """Visit /search/result?types=X pages for each camp type."""
    print("\n[Phase F] Type-filtered search result pages ...")

    type_urls = [
        (f"{SITE_BASE}/search/result?types=autoCamping&adultCnt=2", "오토캠핑"),
        (f"{SITE_BASE}/search/result?types=glamping&adultCnt=2", "글램핑"),
        (f"{SITE_BASE}/search/result?types=caravan&adultCnt=2", "카라반"),
        (f"{SITE_BASE}/search/result?types=pension&adultCnt=2", "펜션"),
        (f"{SITE_BASE}/search/result?types=bungalow&adultCnt=2", "방갈로"),
        (f"{SITE_BASE}/search/result?services=%EC%95%88%EC%8B%AC%EC%B7%A8%EC%86%8C&adultCnt=2", "안심취소"),
        (f"{SITE_BASE}/search/result?services=%EC%9D%B4%EC%A7%80%EC%BA%A0%ED%95%91&adultCnt=2", "이지캠핑"),
    ]

    total_new = 0

    for url, label in type_urls:
        print(f"  [{label}]", end=" ")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            wait_idle(page, timeout=8000)
            time.sleep(1)

            def type_marker():
                return sum(len(v) for v in buckets.get("exhibitions", {}).values())

            scroll_exhaust(page, type_marker, max_rounds=80, stagnant_limit=10)
            wait_idle(page)

            # Merge all exhibition items
            all_items: list[dict] = []
            seen_ids: set[str] = set()
            for items in buckets.get("exhibitions", {}).values():
                for c in items:
                    cid = c.get("id") or c.get("_id")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        all_items.append(c)

            new_n = merge_camps(existing, all_items, f"타입:{label}")
            total_new += new_n
            print(f"-> +{new_n} new")

        except Exception as e:
            print(f"error: {type(e).__name__}")
        time.sleep(1.5)

    return total_new


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    t0 = time.time()
    dedup_path = DATA / "camps_dedup.json"
    existing = load_existing(dedup_path)
    start_count = len(existing)
    print(f"\n{'='*60}")
    print(f"  Starting camp count: {start_count}")
    print(f"{'='*60}\n")

    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    buckets: dict = {}
    handler = make_camp_interceptor(buckets)
    page.on("response", handler)

    phase_results: dict[str, int] = {}

    try:
        # Boot
        print("[boot] CF clearance via /search ...")
        boot(page)
        print(f"  Boot done. Starting phases...")

        # Phase A: Fresh exhibition codes E360-E500
        new_n = phase_fresh_exhibitions(page, buckets, existing)
        phase_results["fresh_exhibitions_E360+"] = new_n
        save_existing(dedup_path, existing)

        # Phase B: Campaigns
        new_n = phase_campaigns(page, buckets, existing)
        phase_results["campaigns"] = new_n
        save_existing(dedup_path, existing)

        # Phase E: Landing pages
        new_n = phase_landing_pages(page, buckets, existing)
        phase_results["landing_pages"] = new_n
        save_existing(dedup_path, existing)

        # Phase F: Type-filtered search
        new_n = phase_type_search(page, buckets, existing)
        phase_results["type_search"] = new_n
        save_existing(dedup_path, existing)

        # Phase C: Sigungu (if still below 1800)
        current = len(existing)
        if current < 1800:
            print(f"\n  At {current} (gap={1800-current}), trying sigungu exhaustion...")
            new_n = phase_sigungu(page, buckets, existing)
            phase_results["sigungu"] = new_n
            save_existing(dedup_path, existing)
        else:
            print(f"\n  At {current} >= 1800, skipping sigungu phase")
            phase_results["sigungu"] = 0

        # Phase D: Keyword search (if still below 1800)
        current = len(existing)
        if current < 1800:
            print(f"\n  At {current} (gap={1800-current}), trying keyword search...")
            new_n = phase_keyword_search(page, buckets, existing)
            phase_results["keyword_search"] = new_n
            save_existing(dedup_path, existing)
        else:
            phase_results["keyword_search"] = 0

    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            b.close()
        except Exception:
            pass

    save_existing(dedup_path, existing)
    elapsed = time.time() - t0
    end_count = len(existing)

    print(f"\n{'='*60}")
    print(f"  START:   {start_count}")
    print(f"  END:     {end_count}  (+{end_count - start_count} new)")
    print(f"  GAP:     {max(0, 1800 - end_count)} to 1800")
    print(f"  Elapsed: {elapsed/60:.1f} min")
    print(f"{'='*60}")
    print("\nPer-phase breakdown:")
    for ph, n in phase_results.items():
        print(f"  {ph:35s}: +{n}")

    if end_count >= 1800:
        print("\n  STATUS: DONE -- 1,800 reached!")
    elif end_count > start_count:
        print(f"\n  STATUS: DONE_WITH_CONCERNS -- reached {end_count}, gap={1800-end_count}")
    else:
        print("\n  STATUS: BLOCKED -- no new camps found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
