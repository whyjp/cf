"""Polite stealth HTTP client — UA rotation, jittered delay, robots.txt enforcement, retry/backoff.

Non-goals (per intent §c.c):
    - CAPTCHA solver, residential proxy, fingerprint spoofing, JS engine emulation.
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


UA_POOL: tuple[str, ...] = (
    # Curated realistic browser UAs. Five entries → satisfies V-1 (≥5).
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
)


@dataclass
class DelayConfig:
    min_s: float = 1.5
    max_s: float = 3.0


@dataclass
class StealthClient:
    base_url: str
    delay: DelayConfig = field(default_factory=DelayConfig)
    timeout_s: float = 20.0
    _robots: Optional[RobotFileParser] = field(default=None, init=False)
    _client: Optional[httpx.AsyncClient] = field(default=None, init=False)
    _last_call: float = field(default=0.0, init=False)
    _ua: str = field(default="", init=False)

    async def __aenter__(self) -> "StealthClient":
        try:
            import h2  # noqa: F401
            http2 = True
        except ImportError:
            http2 = False
        self._client = httpx.AsyncClient(
            timeout=self.timeout_s,
            follow_redirects=True,
            http2=http2,
            headers={
                "Accept": "text/html,application/json,application/xhtml+xml,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
        )
        await self._load_robots()
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()

    async def _load_robots(self) -> None:
        rp = RobotFileParser()
        robots_url = urljoin(self.base_url, "/robots.txt")
        try:
            assert self._client is not None
            r = await self._client.get(robots_url)
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
            else:
                # No robots.txt → allow by RFC 9309
                rp.parse([])
        except httpx.HTTPError:
            rp.parse([])
        self._robots = rp

    def allowed(self, url: str) -> bool:
        if self._robots is None:
            return True
        ua = self._ua or UA_POOL[0]
        return self._robots.can_fetch(ua, url)

    def _pick_ua(self) -> str:
        self._ua = random.choice(UA_POOL)
        return self._ua

    async def _polite_sleep(self) -> None:
        wait = random.uniform(self.delay.min_s, self.delay.max_s)
        elapsed = time.monotonic() - self._last_call
        remaining = wait - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        self._last_call = time.monotonic()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=5, min=5, max=45),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        reraise=True,
    )
    async def _do_get(self, url: str) -> httpx.Response:
        assert self._client is not None
        ua = self._pick_ua()
        await self._polite_sleep()
        r = await self._client.get(url, headers={"User-Agent": ua, "Referer": self.base_url})
        if r.status_code in (403, 429) or r.status_code >= 500:
            r.raise_for_status()
        return r

    async def get(self, path_or_url: str) -> httpx.Response:
        url = path_or_url if path_or_url.startswith("http") else urljoin(self.base_url, path_or_url)
        if not self.allowed(url):
            raise PermissionError(f"robots.txt disallows: {url}")
        return await self._do_get(url)


def average_delay(samples: int = 50, cfg: DelayConfig | None = None) -> float:
    cfg = cfg or DelayConfig()
    return sum(random.uniform(cfg.min_s, cfg.max_s) for _ in range(samples)) / samples
