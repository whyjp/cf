"""Network-capture inspection — discover camfit's actual data endpoints by
intercepting XHR/fetch traffic while the page hydrates.
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

START_URL = sys.argv[1] if len(sys.argv) > 1 else "https://camfit.co.kr/"


def main() -> int:
    print(f"[inspect] launching → {START_URL}")
    b = launch(headless=True, locale="ko-KR", timezone="Asia/Seoul")
    ctx = b.new_context(locale="ko-KR", viewport={"width": 1366, "height": 900})
    page = ctx.new_page()

    log: list[dict] = []
    api_payloads: dict[str, str] = {}

    def on_request(req):
        if req.resource_type in {"xhr", "fetch"}:
            log.append({
                "method": req.method,
                "url": req.url,
                "rt": req.resource_type,
                "post": (req.post_data or "")[:300],
            })

    def on_response(resp):
        try:
            if resp.request.resource_type in {"xhr", "fetch"}:
                ct = (resp.headers.get("content-type") or "")
                # Save non-trivial JSON responses (likely API data)
                if "json" in ct and resp.ok:
                    try:
                        body = resp.body()
                        if len(body) > 200:
                            url = resp.url
                            # short-key for filename
                            key = url.split("?")[0].rsplit("/", 1)[-1] or "root"
                            api_payloads[f"{resp.request.method}_{key}_{len(api_payloads):03d}"] = url
                            (DATA / f"api_{len(api_payloads):03d}.json").write_bytes(body)
                            (DATA / f"api_{len(api_payloads):03d}.url.txt").write_text(url, encoding="utf-8")
                    except Exception as e:
                        pass
        except Exception:
            pass

    page.on("request", on_request)
    page.on("response", on_response)

    try:
        page.goto(START_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(3)
        # Try scrolling to trigger lazy-load XHRs
        for _ in range(8):
            page.mouse.wheel(0, 1500)
            time.sleep(0.6)
        page.wait_for_load_state("networkidle", timeout=10000)
    finally:
        b.close()

    # Summarise
    (DATA / "xhr_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[inspect] xhr/fetch requests captured: {len(log)}")
    seen_hosts: dict[str, int] = {}
    for it in log:
        host = it["url"].split("/")[2] if "://" in it["url"] else "?"
        seen_hosts[host] = seen_hosts.get(host, 0) + 1
    print("[inspect] hosts:")
    for h, c in sorted(seen_hosts.items(), key=lambda x: -x[1]):
        print(f"  {c:>4d}  {h}")
    print()
    print(f"[inspect] API JSON bodies saved: {len(api_payloads)}")
    for k, url in list(api_payloads.items())[:30]:
        print(f"  {k}  ←  {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
