"""Stand-alone CloakBrowser-driven camfit page grabber.

User-run script. NOT imported by the camfit_crawl package — keeps any external-site
fetching deliberately *out-of-band* from the agent's tool surface. Saves rendered HTML
to ``data/`` so the parser/loader can run as pure file processing afterwards.

Usage:
    python scripts/cf_grab.py           # default: home + a handful of pages
    python scripts/cf_grab.py 1 5       # pages 1..5
    python scripts/cf_grab.py --explore # explicit explore path probe
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from cloakbrowser import launch


HERE = Path(__file__).resolve().parent.parent  # camfit-puller/
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)


def _summarise(path: Path, html: str, title: str) -> None:
    cf = "Just a moment" in html
    nx = "__NEXT_DATA__" in html
    cards = len(re.findall(r'/camp/[a-f0-9]{24}', html))
    print(f"  [{path.name:25s}] size={len(html):>7d}  title={title!r:.60s}  CF={cf}  __NEXT_DATA__={nx}  cards={cards}")


def main() -> int:
    args = sys.argv[1:]
    explore = "--explore" in args
    nums = [int(a) for a in args if a.isdigit()]
    pages = nums or list(range(1, 6))

    print("[cloakbrowser] launching headless stealth Chromium...")
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    targets: list[tuple[str, Path]] = [
        ("https://camfit.co.kr/", DATA / "cf_home.html"),
    ]
    if explore:
        targets.append(("https://camfit.co.kr/explore", DATA / "cf_explore.html"))
    for n in pages:
        targets.append((f"https://camfit.co.kr/?page={n}", DATA / f"cf_p{n:02d}.html"))

    try:
        for url, out in targets:
            t0 = time.time()
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # let any client-side hydration / Turnstile resolve
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception as e:
                print(f"  [{out.name}] goto failed: {type(e).__name__}: {e}")
                continue
            time.sleep(2.0)
            html = page.content()
            title = page.title()
            out.write_text(html, encoding="utf-8")
            _summarise(out, html, title)
            print(f"    elapsed {time.time()-t0:.1f}s  status={resp.status if resp else '?'}")
    finally:
        b.close()

    print("[cloakbrowser] done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
