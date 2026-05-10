"""camfit list crawler — JSON endpoint first, then playwright.

Strategy (per intent Q-N1, updated post-handoff):
    1. Try known JSON listing paths via stealth httpx. If 200 + parseable → consume.
    2. If JSON discovery fails AND ``[playwright]`` extra is installed,
       fall back to Playwright + Chromium.
    3. Pagination: stop when a page yields zero new IDs OR hits empty.

None of the fallbacks bypass robots.txt enforcement or anti-bot challenges
(Cloudflare/Akamai). They only handle pages whose markup is JS-rendered.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import httpx
from rich.console import Console

from .models import CampRecord
from .parser import detect_payload, parse_list_html, parse_list_json
from .stealth import StealthClient


CAMFIT_BASE = "https://camfit.co.kr"
console = Console()


# Candidate listing endpoints — first hit wins. Order: most-likely JSON first.
LIST_CANDIDATES = [
    "/api/v1/camps?page={page}&size={size}",
    "/api/camps?page={page}&size={size}",
    "/api/camp/list?page={page}&size={size}",
    "/camp?page={page}",
    "/camps?page={page}",
]

# HTML-rendered list page templates used by the playwright fallback.
HTML_LIST_TEMPLATES = [
    "/camps?page={page}",
    "/camp?page={page}",
    "/list?page={page}",
]


@dataclass
class CrawlConfig:
    base_url: str = CAMFIT_BASE
    page_size: int = 50
    max_pages: int = 200
    discover_only: bool = False  # if True, just confirm endpoints — don't yield


async def _try_candidate(client: StealthClient, tmpl: str, page: int, size: int) -> Optional[tuple[str, list[CampRecord]]]:
    url = tmpl.format(page=page, size=size)
    try:
        r = await client.get(url)
    except (httpx.HTTPError, PermissionError):
        return None
    if r.status_code != 200:
        return None
    body = r.text
    kind = detect_payload(body)
    if kind == "json":
        try:
            recs = parse_list_json(r.json(), base_url=client.base_url)
        except Exception:
            return None
    else:
        recs = parse_list_html(body, base_url=client.base_url)
    return tmpl, recs


async def discover_endpoint(client: StealthClient, size: int) -> Optional[str]:
    for tmpl in LIST_CANDIDATES:
        result = await _try_candidate(client, tmpl, page=1, size=size)
        if result and result[1]:
            tmpl, _ = result
            console.log(f"[crawler] endpoint discovered: {tmpl}")
            return tmpl
    return None


async def crawl(cfg: CrawlConfig | None = None) -> AsyncIterator[CampRecord]:
    cfg = cfg or CrawlConfig()
    seen: set[str] = set()
    async with StealthClient(cfg.base_url) as client:
        endpoint = await discover_endpoint(client, cfg.page_size)
        if endpoint is not None:
            if cfg.discover_only:
                return
            async for rec in _walk_json_endpoint(client, endpoint, cfg, seen):
                yield rec
            return

        # JSON endpoint discovery failed → playwright fallback.
        if cfg.discover_only:
            console.log("[crawler] no JSON endpoint. Try playwright via `crawl` (without --discover-only).")
            return

        async for rec in _walk_via_playwright(cfg, seen):
            yield rec


async def _walk_json_endpoint(client: StealthClient, endpoint: str, cfg: "CrawlConfig", seen: set[str]) -> AsyncIterator[CampRecord]:
    for page in range(1, cfg.max_pages + 1):
        result = await _try_candidate(client, endpoint, page=page, size=cfg.page_size)
        if not result:
            console.log(f"[crawler] page {page}: empty/error → stop")
            break
        _, recs = result
        new = 0
        for rec in recs:
            if rec.id in seen:
                continue
            seen.add(rec.id)
            new += 1
            yield rec
        console.log(f"[crawler] page {page}: +{new} new (total {len(seen)})")
        if new == 0:
            break


async def _walk_via_playwright(cfg: "CrawlConfig", seen: set[str]) -> AsyncIterator[CampRecord]:
    """Fallback — Playwright + Chromium (when JSON endpoint discovery fails)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        console.log(
            "[crawler] Playwright not installed; browser fallback unavailable. "
            "Install: `pip install \".[playwright]\" && playwright install chromium`."
        )
        return
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(locale="ko-KR")
        page = await ctx.new_page()
        try:
            for tmpl in HTML_LIST_TEMPLATES:
                for n in range(1, cfg.max_pages + 1):
                    url = cfg.base_url + tmpl.format(page=n)
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        html = await page.content()
                    except Exception as e:
                        console.log(f"[crawler/playwright] {url}: {type(e).__name__}: {e}")
                        break
                    recs = parse_list_html(html, base_url=cfg.base_url)
                    new = 0
                    for rec in recs:
                        if rec.id in seen:
                            continue
                        seen.add(rec.id)
                        new += 1
                        yield rec
                    console.log(f"[crawler/playwright] {url}: +{new} new (total {len(seen)})")
                    if new == 0:
                        break
                if seen:
                    return
        finally:
            await ctx.close()
            await browser.close()
