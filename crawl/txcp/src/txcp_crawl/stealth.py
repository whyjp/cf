"""Polite stealth httpx client — UA rotation, jittered delay, retry/backoff.

Vendored from camfit-puller stealth.py (CR-3 후속 분리 친화 — 동형 시그니처).
변경점: robots.txt 처리는 호출자에 위임 (txcp 의 robots.txt 는 전역 허용으로 검증됨, FINDINGS.md).
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


# magic-number-traceability: 5 UA pool — camfit-puller V-1 ≥5 만족.
UA_POOL: tuple[str, ...] = (
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
    # magic-number-traceability: 1.5–3.0s = 페이즈 04 §i Recoverable / NFR Polite.
    min_s: float = 1.5
    max_s: float = 3.0


@dataclass
class StealthHttpxClient:
    base_url: str
    delay: DelayConfig = field(default_factory=DelayConfig)
    timeout_s: float = 20.0
    _client: Optional[httpx.AsyncClient] = field(default=None, init=False)
    _last_call: float = field(default=0.0, init=False)
    _ua: str = field(default="", init=False)

    async def __aenter__(self) -> "StealthHttpxClient":
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
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            },
        )
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()

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
        # magic-number-traceability: 3 attempts / 5–45s exp backoff = camfit-puller stealth.py 동형
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=5, min=5, max=45),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
        reraise=True,
    )
    async def post_form(
        self,
        path_or_url: str,
        data: dict[str, str],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        assert self._client is not None
        url = path_or_url if path_or_url.startswith("http") else self.base_url + path_or_url
        ua = self._pick_ua()
        await self._polite_sleep()
        headers = {
            "User-Agent": ua,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": self.base_url + "/",
            "Origin": self.base_url,
        }
        if extra_headers:
            headers.update(extra_headers)
        r = await self._client.post(url, data=data, headers=headers)
        if r.status_code in (429,) or r.status_code >= 500:
            r.raise_for_status()
        return r


def average_delay(samples: int = 50, cfg: DelayConfig | None = None) -> float:
    cfg = cfg or DelayConfig()
    return sum(random.uniform(cfg.min_s, cfg.max_s) for _ in range(samples)) / samples
