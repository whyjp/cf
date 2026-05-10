"""Discover and pull remaining camps from camfit endpoints not yet exhausted.

Strategy:
    1. Boot CloakBrowser to acquire CF clearance cookies.
    2. Use Python requests (with those cookies) to paginate:
       - /v1/collections?key=search (enumerate all collections)
       - /v1/collections/{id}/camps?skip=N (paginate each collection's camps)
       - /v1/exhibitions/camp/{code}?... (re-exhaust large exhibitions)
       - /v1/themes?skip=N (find more theme pages)
       - /v1/themes/{id}/camps?skip=N (paginate each theme's camps)
       - /v1/camp-groups/{id}/camps?skip=N (filter campGroups)
    3. For landing pages and SPA-only content, use actual browser navigation + XHR intercept.
    4. Merge all unique camps into data/camps_dedup.json.

Python requests work because CF clearance cookies pass the bot check.
"""
from __future__ import annotations

import json
import sys
import time
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import requests as req_lib

# Fix Windows console encoding for Korean/emoji output
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from cloakbrowser import launch

HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)

API_BASE = "https://api.camfit.co.kr"
SITE_BASE = "https://camfit.co.kr"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_existing(dedup_path: Path) -> dict[str, dict]:
    existing: dict[str, dict] = {}
    if dedup_path.exists():
        try:
            for c in json.loads(dedup_path.read_text(encoding="utf-8")):
                cid = c.get("id") or c.get("_id")
                if cid:
                    existing[cid] = c
        except Exception as e:
            print(f"  [warn] load failed: {e}")
    return existing


def save_existing(dedup_path: Path, existing: dict[str, dict]) -> None:
    flat = list(existing.values())
    dedup_path.write_text(
        json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8"
    )


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


def api_get(session: req_lib.Session, path: str, params: dict = None, retries: int = 3) -> dict | list | None:
    """GET from api.camfit.co.kr with retry logic."""
    url = f"{API_BASE}{path}"
    for attempt in range(retries):
        try:
            r = session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [rate-limit] 429, waiting {wait}s")
                time.sleep(wait)
            elif r.status_code in (401, 403):
                print(f"  [auth] {r.status_code} at {url}")
                return None
            else:
                print(f"  [http-{r.status_code}] {url}")
                return None
        except Exception as e:
            print(f"  [err] {url}: {e}")
            time.sleep(2)
    return None


def paginate_api(
    session: req_lib.Session,
    path_template: str,
    params_base: dict,
    items_key: str = "auto",
    skip_step: int = 10,
    limit: int = 10,
    max_items: int = 3000,
    polite_delay: float = 0.7,
) -> list[dict]:
    """Paginate a skip/limit API endpoint, return all unique items."""
    all_items: dict[str, dict] = {}
    skip = 0

    while len(all_items) < max_items:
        params = dict(params_base)
        params["skip"] = skip
        params["limit"] = limit

        path = path_template
        data = api_get(session, path, params)

        if data is None:
            break

        # Auto-detect items list
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if items_key == "auto":
                items = (
                    data.get("data")
                    or data.get("camps")
                    or data.get("results")
                    or []
                )
            else:
                items = data.get(items_key) or []
        else:
            break

        if not items:
            break

        new_this_page = 0
        for c in items:
            cid = c.get("id") or c.get("_id")
            if cid and cid not in all_items:
                all_items[cid] = c
                new_this_page += 1

        # Stop if no new items (we're cycling)
        if new_this_page == 0 and skip > 0:
            break

        skip += skip_step
        time.sleep(polite_delay)

        # If returned fewer than limit items, we've hit the end
        if len(items) < limit:
            break

    return list(all_items.values())


def boot_browser_get_session() -> tuple[req_lib.Session, object]:
    """Launch CloakBrowser, visit /search, extract CF cookies into requests session."""
    print("[boot] Launching CloakBrowser to acquire CF clearance...")
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    page.goto(f"{SITE_BASE}/search", wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    time.sleep(2)

    cookies = ctx.cookies()
    print(f"  Got {len(cookies)} cookies")

    session = req_lib.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": f"{SITE_BASE}/",
        "Origin": SITE_BASE,
        "Accept": "application/json",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    })

    # Load all cookies (camfit.co.kr domain cookies work for api.camfit.co.kr)
    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

    # Verify session works
    test = api_get(session, "/v1/exhibitions/camp/E340", {"exhibitionCode": "E340", "skip": "0", "limit": "5"})
    if test:
        print(f"  Session verified: /v1/exhibitions/camp/E340 returned {len(test) if isinstance(test, list) else '?'} items")
    else:
        print("  WARNING: session verification failed")

    return session, b


def scroll_to_exhaust(page, marker_fn, max_rounds: int = 100, stagnant_limit: int = 10):
    last_val = marker_fn()
    stagnant = 0
    for _ in range(max_rounds):
        page.mouse.wheel(0, 2000)
        time.sleep(0.4)
        val = marker_fn()
        if val != last_val:
            last_val = val
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


# ── Phase functions ───────────────────────────────────────────────────────────

def phase_enumerate_collections(session: req_lib.Session, existing: dict) -> tuple[int, list[tuple[str, str]]]:
    """Enumerate all collections and add their first-page camps."""
    print("\n[Phase 1] Enumerate all collections via API pagination...")
    all_colls: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    total_new = 0
    skip = 0

    while True:
        data = api_get(session, "/v1/collections", {"key": "search", "skip": skip, "limit": 5})
        if not data or not isinstance(data, dict):
            break
        items = data.get("data") or []
        if not items:
            break

        for c in items:
            cid = c.get("_id") or c.get("id")
            cname = c.get("name") or "?"
            if cid and cid not in seen_ids:
                seen_ids.add(cid)
                all_colls.append((cid, cname))
                # Merge first-page camps
                camps = c.get("camps") or []
                new_n = merge_camps(existing, camps, f"콜렉션:{cname}")
                total_new += new_n

        has_next = data.get("hasNext", False)
        print(f"  skip={skip}: {len(items)} colls, hasNext={has_next}")
        if not has_next:
            break
        skip += 5
        time.sleep(0.7)

    print(f"  Total collections: {len(all_colls)}, new camps from first pages: {total_new}")
    for cid, cname in all_colls:
        print(f"    {cid} - {cname}")

    return total_new, all_colls


def phase_paginate_collections(session: req_lib.Session, existing: dict, all_colls: list[tuple[str, str]]) -> int:
    """Paginate each collection's camps fully."""
    print(f"\n[Phase 2] Paginate {len(all_colls)} collections' camps...")
    total_new = 0

    for ci, (cid, cname) in enumerate(all_colls, 1):
        print(f"  [{ci}/{len(all_colls)}] '{cname}'", end="")
        items = paginate_api(
            session,
            f"/v1/collections/{cid}/camps",
            {},
            max_items=500,
            polite_delay=0.6,
        )
        new_n = merge_camps(existing, items, f"콜렉션:{cname}")
        total_new += new_n
        print(f" -> {len(items)} camps, +{new_n} new")

    print(f"  Total new from collection pagination: {total_new}")
    return total_new


def phase_exhibitions_exhaustive(session: req_lib.Session, existing: dict) -> int:
    """Exhaustively paginate all known + probed exhibition codes."""
    print("\n[Phase 3] Exhibition exhaustive pagination...")

    # Build exhibit list from what we know
    known_codes = [
        # High-value exhibitions from home/main
        "E340",  # 반려동물 (1000 claimed)
        "E46",   # 나만 알고 싶은 (609 claimed)
        "E339",  # 타프존 (221 claimed)
        "E351",  # 스프링캠프 (219 claimed)
        "E164",  # 지금 가기 좋은 (143 claimed)
        "E82",   # 인기 급상승 (147 claimed)
        "E315",  # 신설 숙소 (86 claimed)
        "E352",  # 위클리픽 (49 claimed)
        "E330",  # 차박캠핑 (42 claimed)
        "E39",   # 신규 입점 (26 claimed)
        # From curations/expanded scan
        "E355",
        "E354",
        "E353",
        "E129",
        # High-hit from existing _collections tags
        "E236", "E258", "E282", "E297", "E308",
        "E67", "E196", "E217", "E42", "E198",
        "E189", "E240", "E190", "E188", "E187",
        "E209", "E232", "E238", "E14", "E170",
        "E176", "E185", "E186", "E194",
        "E212", "E219", "E244", "E245",
        "E255", "E261", "E265", "E267",
        "E270", "E272", "E273", "E274", "E278",
        "E284", "E287", "E294", "E295", "E296",
        "E301", "E303", "E305",
        "E310", "E311", "E313", "E314",
        "E316", "E320", "E321", "E322",
        "E328", "E336", "E337", "E338",
        "E341", "E343", "E344", "E345",
        "E349", "E350",
        "E356", "E357", "E358", "E359",
        "E43", "E47", "E64",
    ]
    # Also probe any we haven't seen
    seen_codes = set(known_codes)
    # Probe codes not yet known
    probe_extra = [f"E{n}" for n in range(1, 400) if f"E{n}" not in seen_codes]

    total_new = 0
    empty_streak = 0

    print(f"  Known codes: {len(known_codes)}, probe extra: {len(probe_extra)}")

    # First do known codes
    for code in known_codes:
        items = paginate_api(
            session,
            f"/v1/exhibitions/camp/{code}",
            {"exhibitionCode": code},
            max_items=2000,
            polite_delay=0.6,
        )
        new_n = merge_camps(existing, items, f"전시:{code}")
        total_new += new_n
        if items:
            print(f"  {code}: {len(items)} camps, +{new_n} new")
        else:
            print(f"  {code}: empty")

    # Then probe unknown codes
    print(f"\n  Probing {len(probe_extra)} unknown codes...")
    for code in probe_extra:
        # Quick check: just get skip=0
        data = api_get(session, f"/v1/exhibitions/camp/{code}", {"exhibitionCode": code, "skip": "0", "limit": "10"})
        if data is None:
            empty_streak += 1
            if empty_streak >= 20:
                print(f"  {code}: 20 empty streak, stopping probe")
                break
            continue

        if isinstance(data, list):
            items_check = data
        else:
            items_check = data.get("data") or data.get("camps") or []

        if not items_check:
            empty_streak += 1
            if empty_streak >= 20:
                print(f"  {code}: 20 empty streak, stopping probe")
                break
            continue

        empty_streak = 0
        # Has data, paginate fully
        all_items = list({c.get("id") or c.get("_id"): c for c in items_check if c.get("id") or c.get("_id")}.values())

        # Continue pagination
        more = paginate_api(
            session,
            f"/v1/exhibitions/camp/{code}",
            {"exhibitionCode": code},
            max_items=2000,
            polite_delay=0.6,
        )
        for c in more:
            cid = c.get("id") or c.get("_id")
            if cid:
                all_items.append(c)

        new_n = merge_camps(existing, all_items, f"전시:{code}")
        total_new += new_n
        print(f"  {code}: {len(all_items)} camps, +{new_n} NEW")
        time.sleep(0.5)

    print(f"\n  Total new from exhibitions: {total_new}")
    return total_new


def phase_themes_exhaustive(session: req_lib.Session, existing: dict) -> int:
    """Enumerate all themes and paginate their camps."""
    print("\n[Phase 4] Themes exhaustive pagination...")
    total_new = 0

    # Enumerate all themes
    all_themes: dict[str, str] = {}  # id -> name
    for skip in range(0, 200, 10):
        data = api_get(session, "/v1/themes", {"skip": skip, "limit": 10})
        if not data or not isinstance(data, dict):
            break
        themes = data.get("data") or []
        if not themes:
            break
        for t in themes:
            tid = t.get("id") or t.get("_id")
            tname = t.get("name") or "?"
            if tid:
                all_themes[tid] = tname
        print(f"  themes skip={skip}: {len(themes)} themes")
        if len(themes) < 10:
            break
        time.sleep(0.7)

    print(f"  Total themes discovered: {len(all_themes)}")
    for tid, tname in all_themes.items():
        print(f"    {tid} - {tname}")

    # Paginate each theme's camps
    for ti, (tid, tname) in enumerate(all_themes.items(), 1):
        print(f"  [{ti}/{len(all_themes)}] theme '{tname}'", end="")
        items = paginate_api(
            session,
            f"/v1/themes/{tid}/camps",
            {},
            max_items=500,
            polite_delay=0.6,
        )
        new_n = merge_camps(existing, items, f"테마:{tname}")
        total_new += new_n
        print(f" -> {len(items)} camps, +{new_n} new")

    print(f"  Total new from themes: {total_new}")
    return total_new


def phase_campgroups(session: req_lib.Session, existing: dict) -> int:
    """Pull camps from known campGroup IDs."""
    print("\n[Phase 5] CampGroups from filter data...")

    campgroup_ids = [
        ("69cf84ce1dffc8001dcf45e1", "찾아오는체험"),
        ("69cf303a2b1b88001d0fe92c", "펫니스태안"),
        ("67e3963c456e89001d3e6310", "이지캠핑"),
    ]

    total_new = 0
    for gid, gname in campgroup_ids:
        print(f"  campgroup '{gname}' ({gid})", end="")
        items = paginate_api(
            session,
            f"/v1/camp-groups/{gid}/camps",
            {},
            max_items=500,
            polite_delay=0.7,
        )
        new_n = merge_camps(existing, items, f"캠프그룹:{gname}")
        total_new += new_n
        print(f" -> {len(items)} camps, +{new_n} new")

    return total_new


def phase_landing_pages(page, existing: dict) -> int:
    """Visit landing pages and capture XHR for their camps."""
    print("\n[Phase 6] Landing pages (browser navigation + XHR capture)...")

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

    captured_by_lid: dict[str, list[dict]] = {lid: [] for lid in landing_ids}
    captured_exhibitions: dict[str, list[dict]] = {}

    _LANDING_CAMPS_RE = re.compile(
        r"/v1/landings/([a-f0-9]{24})/camps\?.*skip=(\d+)"
    )
    _EXHIBITION_RE = re.compile(
        r"/v1/exhibitions/camp/([A-Z0-9]+)\?.*skip=(\d+)"
    )

    def on_resp(resp):
        try:
            if not resp.ok:
                return
            url = resp.url
            ct = resp.headers.get("content-type") or ""
            if "json" not in ct:
                return
            body = resp.body()
            payload = json.loads(body)

            m = _LANDING_CAMPS_RE.search(url)
            if m:
                lid = m.group(1)
                if lid in captured_by_lid:
                    if isinstance(payload, list):
                        items = payload
                    else:
                        items = payload.get("data") or payload.get("camps") or []
                    if items:
                        captured_by_lid[lid].extend(items)
                        print(f"    [xhr] landing/{lid[:8]} -> {len(items)} camps")
                return

            m = _EXHIBITION_RE.search(url)
            if m:
                code = m.group(1)
                if isinstance(payload, list):
                    items = payload
                else:
                    items = payload.get("data") or payload.get("camps") or []
                if items:
                    captured_exhibitions.setdefault(code, []).extend(items)
                return

        except Exception:
            pass

    page.on("response", on_resp)
    total_new = 0

    for li, lid in enumerate(landing_ids, 1):
        print(f"  [{li}/{len(landing_ids)}] landing {lid[:12]}...")
        try:
            page.goto(f"{SITE_BASE}/landing/{lid}",
                      wait_until="domcontentloaded", timeout=30000)
            wait_idle(page)
            time.sleep(1)

            def land_marker():
                return len(captured_by_lid.get(lid, [])) + sum(len(v) for v in captured_exhibitions.values())

            scroll_to_exhaust(page, land_marker, max_rounds=60, stagnant_limit=8)
            wait_idle(page)

            items = captured_by_lid.get(lid, [])
            new_n = merge_camps(existing, items, f"랜딩:{lid[:8]}")
            total_new += new_n
            print(f"    -> {len(items)} landing camps, +{new_n} new")

        except Exception as e:
            print(f"    !! {type(e).__name__}: {e}")
        time.sleep(1.5)

    # Merge exhibition camps captured from landing pages
    for code, items in captured_exhibitions.items():
        new_n = merge_camps(existing, items, f"전시:{code}")
        if new_n > 0:
            print(f"  Landing exhibition {code}: +{new_n} new")
            total_new += new_n

    page.remove_listener("response", on_resp)
    return total_new


def phase_curations_extended(session: req_lib.Session, page, existing: dict) -> int:
    """Pull curations beyond page 1 and visit their exhibitions/landings."""
    print("\n[Phase 7] Extended curations...")

    total_new = 0
    exhibition_codes_to_pull: set[str] = set()
    landing_ids_to_pull: set[str] = set()

    for page_n in range(2, 15):
        data = api_get(session, "/v2/curations/with-biz", {"place": "main", "page": page_n, "pageSize": 50})
        if not data:
            break
        curations = data.get("curations") or []
        if not curations:
            print(f"  curation page {page_n}: empty -> stopping")
            break
        print(f"  curation page {page_n}: {len(curations)} curations")
        for curation in curations:
            for banner in curation.get("banners", []):
                link = banner.get("link", "")
                if "/exhibition/" in link:
                    code = link.split("/exhibition/")[1].split("?")[0].strip()
                    if code:
                        exhibition_codes_to_pull.add(code)
                elif "/landing/" in link:
                    lid = link.split("/landing/")[1].split("?")[0].strip()
                    if lid:
                        landing_ids_to_pull.add(lid)
        time.sleep(1)

    print(f"  Found in curations: {len(exhibition_codes_to_pull)} exhibition codes, {len(landing_ids_to_pull)} landings")

    # Pull these exhibitions via API (quick since we likely already have them from phase 3)
    for code in exhibition_codes_to_pull:
        items = paginate_api(
            session,
            f"/v1/exhibitions/camp/{code}",
            {"exhibitionCode": code},
            max_items=1000,
            polite_delay=0.6,
        )
        new_n = merge_camps(existing, items, f"전시:{code}")
        if new_n > 0:
            print(f"  Exhibition {code}: {len(items)} camps, +{new_n} NEW")
            total_new += new_n

    # Pull landing pages via browser
    captured_by_lid: dict[str, list[dict]] = {lid: [] for lid in landing_ids_to_pull}

    _LANDING_CAMPS_RE = re.compile(
        r"/v1/landings/([a-f0-9]{24})/camps\?.*skip=(\d+)"
    )

    def on_resp2(resp):
        try:
            if not resp.ok:
                return
            url = resp.url
            ct = resp.headers.get("content-type") or ""
            if "json" not in ct:
                return
            m = _LANDING_CAMPS_RE.search(url)
            if m:
                lid = m.group(1)
                if lid in captured_by_lid:
                    body = resp.body()
                    payload = json.loads(body)
                    if isinstance(payload, list):
                        items = payload
                    else:
                        items = payload.get("data") or payload.get("camps") or []
                    captured_by_lid[lid].extend(items)
        except Exception:
            pass

    page.on("response", on_resp2)

    for lid in landing_ids_to_pull:
        print(f"  Landing {lid[:12]}...")
        try:
            page.goto(f"{SITE_BASE}/landing/{lid}",
                      wait_until="domcontentloaded", timeout=30000)
            wait_idle(page)
            time.sleep(1)

            def land_marker2():
                return len(captured_by_lid.get(lid, []))

            scroll_to_exhaust(page, land_marker2, max_rounds=50, stagnant_limit=8)
            wait_idle(page)

            items = captured_by_lid.get(lid, [])
            new_n = merge_camps(existing, items, f"랜딩:{lid[:8]}")
            total_new += new_n
            if items:
                print(f"    -> {len(items)} camps, +{new_n} new")

        except Exception as e:
            print(f"    !! {type(e).__name__}")
        time.sleep(1.5)

    page.remove_listener("response", on_resp2)
    return total_new


def phase_sigungu_exhaustion(session: req_lib.Session, page, existing: dict) -> int:
    """Use browser + XHR intercept to find camps via city/sigungu filter combos.

    The search endpoint used is /v1/collections?key=search but with region context.
    We intercept all exhibition XHRs triggered by the SPA filter.
    """
    print("\n[Phase 8] City+sigungu exhaustion via browser...")

    sigungu_map = {
        "강원": [
            "평창군", "홍천군", "인제군", "양양군", "고성군", "속초시",
            "강릉시", "정선군", "춘천시", "원주시", "태백시", "영월군",
            "철원군", "화천군", "양구군", "삼척시",
        ],
        "경기": [
            "가평군", "양평군", "포천시", "여주시", "연천군",
            "파주시", "광주시", "용인시", "안성시",
        ],
        "충남": [
            "태안군", "보령시", "서산시", "당진시", "예산군",
            "홍성군", "공주시", "부여군",
        ],
        "충북": [
            "제천시", "단양군", "충주시", "괴산군", "보은군", "옥천군",
        ],
        "경북": [
            "영주시", "봉화군", "울진군", "청송군", "영양군",
            "문경시", "상주시", "경주시",
        ],
        "경남": [
            "남해군", "하동군", "함양군", "거창군", "합천군",
            "통영시", "고성군",
        ],
        "전남": [
            "여수시", "순천시", "구례군", "담양군",
            "완도군", "진도군", "해남군",
        ],
        "전북": [
            "무주군", "진안군", "장수군", "남원시",
        ],
        "제주": ["제주시", "서귀포시"],
    }

    captured_exh: dict[str, list[dict]] = {}
    _EXHIBITION_RE = re.compile(
        r"/v1/exhibitions/camp/([A-Z0-9]+)\?.*skip=(\d+)"
    )

    def on_resp_sg(resp):
        try:
            if not resp.ok:
                return
            url = resp.url
            ct = resp.headers.get("content-type") or ""
            if "json" not in ct:
                return
            m = _EXHIBITION_RE.search(url)
            if m:
                code, skip = m.group(1), int(m.group(2))
                body = resp.body()
                payload = json.loads(body)
                if isinstance(payload, list):
                    items = payload
                else:
                    items = payload.get("data") or payload.get("camps") or []
                if items:
                    key = f"{code}:{skip}"
                    captured_exh.setdefault(key, items)
        except Exception:
            pass

    page.on("response", on_resp_sg)
    total_new = 0

    for city, sigungu_list in sigungu_map.items():
        for sigungu in sigungu_list:
            print(f"  [{city}/{sigungu}]")
            prev_total = sum(len(v) for v in captured_exh.values())
            try:
                page.goto(f"{SITE_BASE}/search",
                          wait_until="domcontentloaded", timeout=30000)
                wait_idle(page, timeout=8000)
                time.sleep(1)

                # Click city chip
                try:
                    page.click(f"text={city}", timeout=3000)
                    wait_idle(page, timeout=5000)
                    time.sleep(0.5)
                except Exception:
                    pass

                # Click sigungu chip
                try:
                    page.click(f"text={sigungu}", timeout=3000)
                    wait_idle(page, timeout=5000)
                    time.sleep(0.5)
                except Exception:
                    pass

                def sg_marker():
                    return sum(len(v) for v in captured_exh.values())

                scroll_to_exhaust(page, sg_marker, max_rounds=50, stagnant_limit=8)
                wait_idle(page)

            except Exception as e:
                print(f"    !! {type(e).__name__}")

            # Calculate new items
            cur_total = sum(len(v) for v in captured_exh.values())
            new_items_count = cur_total - prev_total
            if new_items_count > 0:
                # Merge all newly captured items
                all_new: list[dict] = []
                for items in captured_exh.values():
                    all_new.extend(items)
                new_n = merge_camps(existing, all_new, f"시군구:{city}/{sigungu}")
                if new_n > 0:
                    print(f"    -> +{new_n} new camps")
                    total_new += new_n

            time.sleep(1.0)

    page.remove_listener("response", on_resp_sg)
    return total_new


def main() -> int:
    t0 = time.time()
    dedup_path = DATA / "camps_dedup.json"
    existing = load_existing(dedup_path)
    start_count = len(existing)
    print(f"\n{'='*60}")
    print(f"  Starting camp count: {start_count}")
    print(f"{'='*60}\n")

    # Boot browser + get session
    session, browser = boot_browser_get_session()
    ctx = browser.new_context(locale="ko-KR", viewport={"width": 1440, "height": 900})
    page = ctx.new_page()

    # Boot page for browser phases
    page.goto(f"{SITE_BASE}/search", wait_until="domcontentloaded", timeout=60000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    time.sleep(2)

    phase_results: dict[str, int] = {}

    try:
        # Phase 1: Enumerate all collections
        new_n, all_colls = phase_enumerate_collections(session, existing)
        phase_results["collections_enumeration"] = new_n
        save_existing(dedup_path, existing)
        print(f"  Saved. Total: {len(existing)}")

        # Phase 2: Paginate each collection's camps fully
        new_n = phase_paginate_collections(session, existing, all_colls)
        phase_results["collections_pagination"] = new_n
        save_existing(dedup_path, existing)
        print(f"  Saved. Total: {len(existing)}")

        # Phase 3: Exhaustively paginate all exhibitions
        new_n = phase_exhibitions_exhaustive(session, existing)
        phase_results["exhibitions"] = new_n
        save_existing(dedup_path, existing)
        print(f"  Saved. Total: {len(existing)}")

        # Phase 4: Themes exhaustive
        new_n = phase_themes_exhaustive(session, existing)
        phase_results["themes"] = new_n
        save_existing(dedup_path, existing)
        print(f"  Saved. Total: {len(existing)}")

        # Phase 5: CampGroups
        new_n = phase_campgroups(session, existing)
        phase_results["campgroups"] = new_n
        save_existing(dedup_path, existing)
        print(f"  Saved. Total: {len(existing)}")

        # Phase 6: Landing pages (browser)
        new_n = phase_landing_pages(page, existing)
        phase_results["landings"] = new_n
        save_existing(dedup_path, existing)
        print(f"  Saved. Total: {len(existing)}")

        # Phase 7: Extended curations
        new_n = phase_curations_extended(session, page, existing)
        phase_results["curations"] = new_n
        save_existing(dedup_path, existing)
        print(f"  Saved. Total: {len(existing)}")

        # Phase 8: Sigungu exhaustion (only if still below 1800)
        current = len(existing)
        if current < 1800:
            print(f"\n  Still at {current} (gap={1800-current}), doing sigungu exhaustion...")
            new_n = phase_sigungu_exhaustion(session, page, existing)
            phase_results["sigungu"] = new_n
            save_existing(dedup_path, existing)
            print(f"  Saved. Total: {len(existing)}")
        else:
            print(f"\n  At {current} (>= 1800), skipping sigungu phase")

    except Exception as e:
        print(f"\n[FATAL] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            browser.close()
        except Exception:
            pass

    # Final save
    save_existing(dedup_path, existing)
    elapsed = time.time() - t0
    end_count = len(existing)

    print(f"\n{'='*60}")
    print(f"  START: {start_count}")
    print(f"  END:   {end_count}  (+{end_count - start_count} new camps)")
    print(f"  GAP to 1800: {max(0, 1800 - end_count)}")
    print(f"  Elapsed: {elapsed/60:.1f} min")
    print(f"{'='*60}")
    print("\nPer-phase breakdown:")
    for ph, n in phase_results.items():
        print(f"  {ph:30s}: +{n}")

    if end_count >= 1800:
        print("\n  STATUS: DONE -- 1,800 reached!")
    elif end_count > start_count:
        print(f"\n  STATUS: DONE_WITH_CONCERNS -- reached {end_count}, gap={1800-end_count}")
    else:
        print("\n  STATUS: BLOCKED -- no new camps found")

    return 0


if __name__ == "__main__":
    sys.exit(main())
