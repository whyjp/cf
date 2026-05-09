"""Expand camfit camp dataset by exhausting all exhibition pages.

Discovery:
    The SPA uses /v1/exhibitions/camp/{code}?exhibitionCode={code}&skip=N&limit=10
    to paginate camps in each exhibition. Exhibition codes are in /v2/home/main
    as campExhibitions + additionalExhibitions (codes like E39, E351, etc.).

    Additionally, the /v1/collections?key=search endpoint is already partially
    exhausted; we try a wider range of sequential codes to find more exhibitions.

Strategy:
    1. Boot via /search (Cloudflare cookie acquisition).
    2. Navigate to /exhibition/{code} for each known + probed code.
       Scroll to exhaust all pagination (intercept /v1/exhibitions/camp/* XHRs).
    3. Merge all camps into data/camps_dedup.json preserving prior _collections.
    4. Report: start count, end count, per-source breakdown.

Polite: ~1.5s between clicks, natural scroll pacing (~10 px/scroll).
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
DATA.mkdir(parents=True, exist_ok=True)
RI = DATA / "region_inspect"
RI.mkdir(parents=True, exist_ok=True)


# ── Exhibition codes discovered from v2/home/main ─────────────────────────────
# These are the codes embedded in the home-page exhibitions list.
# numOfCamps column shows how many camps are in each.
KNOWN_CODES = [
    "E39",   # 신규 입점 (26)
    "E351",  # 스프링캠프 (219)
    "E164",  # 지금 가기 좋은 (143)
    "E46",   # 나만 알고 싶은 (609)
    "E330",  # 차박캠핑 (42)
    "E352",  # 위클리픽 (49)
    "E339",  # 타프존 (221)
    "E340",  # 반려동물 (1000)
    "E82",   # 인기 급상승 (147)
    "E315",  # 신설 숙소 (86)
]

# Probe sequential codes: themes/collections may use codes like E1..E360
# We'll try these but skip quickly if empty.
PROBE_CODES = [f"E{n}" for n in range(1, 360) if f"E{n}" not in KNOWN_CODES]


def scroll_exhaust(page, captured: dict, code: str, max_rounds: int = 120) -> int:
    """Scroll until no new skip values appear for this exhibition code.
    Returns number of new pages captured."""
    last_max_skip = -1
    stagnant = 0
    new_pages = 0
    for _ in range(max_rounds):
        page.mouse.wheel(0, 2000)
        time.sleep(0.4)
        cur_skips = [s for (c, s) in captured.keys() if c == code]
        cur_max = max(cur_skips) if cur_skips else -1
        if cur_max > last_max_skip:
            last_max_skip = cur_max
            new_pages += 1
            stagnant = 0
        else:
            stagnant += 1
        if stagnant >= 8:
            break
    return new_pages


def visit_exhibition(page, code: str, captured: dict) -> int:
    """Navigate to /exhibition/{code} and scroll to exhaust pagination."""
    page.goto(f"https://camfit.co.kr/exhibition/{code}",
              wait_until="domcontentloaded", timeout=30000)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    time.sleep(1.0)
    rounds = scroll_exhaust(page, captured, code)
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    return rounds


def main() -> int:
    # ── Load existing dedup ───────────────────────────────────────────────────
    dedup_path = DATA / "camps_dedup.json"
    existing: dict[str, dict] = {}
    if dedup_path.exists():
        try:
            for c in json.loads(dedup_path.read_text(encoding="utf-8")):
                cid = c.get("id") or c.get("_id")
                if cid:
                    existing[cid] = c
        except Exception:
            pass
    start_count = len(existing)
    print(f"[start] existing camps: {start_count}")

    # ── Launch browser ────────────────────────────────────────────────────────
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    # captured[(code, skip)] = list of camp dicts
    captured: dict[tuple[str, int], list] = {}

    def on_response(resp):
        try:
            url = resp.url
            if not resp.ok:
                return
            ct = resp.headers.get("content-type") or ""
            if "json" not in ct:
                return
            if "/v1/exhibitions/camp/" not in url:
                return
            # Extract code and skip
            path = url.split("/v1/exhibitions/camp/")[1]
            code_part = path.split("?")[0]
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(url).query)
            skip = int(q.get("skip", ["0"])[0])
            if (code_part, skip) not in captured:
                body = resp.body()
                data = json.loads(body)
                if isinstance(data, list):
                    captured[(code_part, skip)] = data
                    print(f"    [xhr] {code_part} skip={skip:>4d} → {len(data)} camps")
                elif isinstance(data, dict):
                    # Some codes return {data: [...], ...} or empty
                    inner = data.get("data") or data.get("camps") or []
                    captured[(code_part, skip)] = inner if isinstance(inner, list) else []
        except Exception:
            pass

    page.on("response", on_response)

    # ── Bootstrap: visit /search to acquire CF clearance ─────────────────────
    print("[boot] /search (CF clearance) ...")
    page.goto("https://camfit.co.kr/search", wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    time.sleep(2)

    # ── Phase 1: Pull known high-value exhibitions ────────────────────────────
    print(f"\n[phase-1] pulling {len(KNOWN_CODES)} known exhibitions ...")
    code_camp_counts: dict[str, int] = {}
    for ci, code in enumerate(KNOWN_CODES, 1):
        pre = len(captured)
        try:
            print(f"  [{ci}/{len(KNOWN_CODES)}] exhibition {code}")
            visit_exhibition(page, code, captured)
        except Exception as e:
            print(f"    error: {type(e).__name__}: {e}")
            try:
                page.goto("https://camfit.co.kr/search",
                          wait_until="domcontentloaded", timeout=30000)
                time.sleep(1.5)
            except Exception:
                pass
        pages = len(captured) - pre
        items = sum(len(v) for (c, s), v in captured.items() if c == code)
        code_camp_counts[code] = items
        print(f"    → {pages} pages, {items} camp entries")

    # ── Phase 2: Probe sequential codes ──────────────────────────────────────
    print(f"\n[phase-2] probing {len(PROBE_CODES)} sequential codes ...")
    empty_streak = 0
    MAX_EMPTY_STREAK = 30  # stop if 30 consecutive codes are empty
    probed = 0
    for code in PROBE_CODES:
        probed += 1
        pre_items = sum(len(v) for (c, s), v in captured.items() if c == code)
        try:
            print(f"  probe {code} ...", end=" ", flush=True)
            # Quick probe: just navigate, wait for initial XHR, don't scroll much
            page.goto(f"https://camfit.co.kr/exhibition/{code}",
                      wait_until="domcontentloaded", timeout=15000)
            try:
                page.wait_for_load_state("networkidle", timeout=6000)
            except Exception:
                pass
            time.sleep(0.8)
            # Check if we got any data for this code
            items_here = sum(len(v) for (c, s), v in captured.items() if c == code)
            if items_here > 0:
                print(f"has data ({items_here}) → scroll exhaust")
                scroll_exhaust(page, captured, code, max_rounds=60)
                total = sum(len(v) for (c, s), v in captured.items() if c == code)
                code_camp_counts[code] = total
                print(f"    → {total} camp entries")
                empty_streak = 0
            else:
                print("empty")
                empty_streak += 1
                if empty_streak >= MAX_EMPTY_STREAK:
                    print(f"  {MAX_EMPTY_STREAK} empty codes in a row — stop probing")
                    break
        except Exception as e:
            print(f"  error: {type(e).__name__}")
            empty_streak += 1

    b.close()

    # ── Merge into dedup ──────────────────────────────────────────────────────
    print("\n[merge] aggregating all exhibitions ...")
    new_count = 0
    for (code, skip), items in captured.items():
        for c in items:
            cid = c.get("id") or c.get("_id")
            if not cid:
                continue
            if cid not in existing:
                c2 = dict(c)
                c2.setdefault("_collections", [])
                existing[cid] = c2
                new_count += 1
            tag = f"전시:{code}"
            cols = existing[cid].setdefault("_collections", [])
            if tag not in cols:
                cols.append(tag)

    flat = list(existing.values())
    dedup_path.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")

    end_count = len(flat)
    print(f"\n{'='*60}")
    print(f"  start: {start_count}")
    print(f"  end:   {end_count}  (+{new_count} new camps)")
    print(f"  target was 1,800 -- {'REACHED' if end_count >= 1800 else f'gap: {1800 - end_count}'}")
    print(f"{'='*60}")

    # Per-source breakdown (top 10)
    print("\nTop sources by camp entries captured:")
    top = sorted(code_camp_counts.items(), key=lambda x: -x[1])[:15]
    for code, cnt in top:
        print(f"  {code:>6s}: {cnt:>5d} entries")

    return 0


if __name__ == "__main__":
    sys.exit(main())
