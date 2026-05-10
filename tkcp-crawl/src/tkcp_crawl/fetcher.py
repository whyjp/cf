"""Fetcher Protocol + impls.

Plan u1 winner: HttpxFetcher 를 primary 로. ChromeFetcher 는 후속 PR 발동 placeholder
(인터페이스만 정의 — *_internal/* 가 아니라 public Protocol — 후속 PR 의 add-on 구현 친화).
"""
from __future__ import annotations

from typing import Protocol

import httpx

from tkcp_crawl.stealth import StealthHttpxClient


class Fetcher(Protocol):
    async def post_form(
        self,
        path: str,
        data: dict[str, str],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> dict: ...


class HttpxFetcher:
    def __init__(self, base_url: str, timeout_s: float = 20.0) -> None:
        self._client = StealthHttpxClient(base_url=base_url, timeout_s=timeout_s)
        self._opened = False

    async def open(self) -> None:
        if not self._opened:
            await self._client.__aenter__()
            self._opened = True

    async def close(self) -> None:
        if self._opened:
            await self._client.__aexit__(None, None, None)
            self._opened = False

    async def post_form(
        self,
        path: str,
        data: dict[str, str],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> dict:
        await self.open()
        r: httpx.Response = await self._client.post_form(path, data, extra_headers=extra_headers)
        r.raise_for_status()
        return r.json()


class ChromeFetcher:
    """cloak chrome (Playwright/Camoufox) fallback — 본 PR 비발동.

    후속 PR 에서 botmanager 차단 시 발동. 인터페이스 (Fetcher Protocol) 동형.
    구현 가이드는 README 의 *2-tier fetcher* 섹션 참조.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    async def open(self) -> None:
        raise NotImplementedError(
            "ChromeFetcher 는 향후 PR 에서 구현 예정 — botmanager 차단 시 발동. "
            "현재 path: HttpxFetcher 가 ax_list_search.hbb JSON 직접 호출."
        )

    async def close(self) -> None:
        return None

    async def post_form(
        self,
        path: str,
        data: dict[str, str],
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> dict:
        raise NotImplementedError(
            "ChromeFetcher.post_form — see open()."
        )
