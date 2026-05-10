"""One-off: fetch camfit.co.kr home via Scrapling (WSL venv with Camoufox)."""
from __future__ import annotations

from pathlib import Path

from scrapling.fetchers import StealthyFetcher

OUT = Path("/mnt/d/github/cf/camfit-puller/data/cf_home.html")


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    p = StealthyFetcher.fetch(
        "https://camfit.co.kr/",
        headless=True,
        solve_cloudflare=True,
        network_idle=True,
    )
    print("STATUS", p.status)
    print("SIZE", len(p.html_content))
    print("TITLE", p.css("title::text").get())
    OUT.write_text(p.html_content, encoding="utf-8")
    print("SAVED", OUT)


if __name__ == "__main__":
    main()
