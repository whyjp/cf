"""smoke — 실 사이트 1 페이지 호출. CI 비활성. TXCP_LIVE=1 시에만 실행.

usage:
    TXCP_LIVE=1 uv run python -m pytest tests/smoke_txcp_real.py -v
또는:
    TXCP_LIVE=1 uv run python tests/smoke_txcp_real.py
"""
from __future__ import annotations

import asyncio
import os

import pytest

from txcp_crawl.adapter import TkcpAdapter
from txcp_crawl.fetcher import HttpxFetcher
from txcp_crawl.settings import Settings


pytestmark = [pytest.mark.live, pytest.mark.asyncio]


SKIP_REASON = "TXCP_LIVE=1 not set — smoke test disabled"


@pytest.mark.skipif(os.environ.get("TXCP_LIVE") != "1", reason=SKIP_REASON)
async def test_one_page_real():
    settings = Settings()
    adapter = TkcpAdapter()
    fetcher = HttpxFetcher(base_url=settings.base_url)
    await fetcher.open()
    try:
        payload = adapter.build_payload(1, site_tp="BB000")
        raw = await fetcher.post_form(adapter.LIST_PATH, payload)
        result = adapter.parse_camp_list_response(raw)
    finally:
        await fetcher.close()
    assert result.total_count > 5000, f"expected >5000 camps, got {result.total_count}"
    assert len(result.records) >= 10, f"page should have >=10 records, got {len(result.records)}"
    first = result.records[0]
    assert first.region_sido is not None
    # 한글 syllable check (U+AC00..D7A3)
    assert any(0xAC00 <= ord(c) <= 0xD7A3 for c in (first.region_sido or "")), (
        f"region_sido should be Korean: {first.region_sido!r}"
    )
    print(
        f"[smoke OK] total={result.total_count} page1={len(result.records)} "
        f"first={first.id}/{first.name}/{first.region_sido}/{first.region_sigungu}"
    )


if __name__ == "__main__":
    if os.environ.get("TXCP_LIVE") != "1":
        print("Set TXCP_LIVE=1 to run smoke test")
        raise SystemExit(0)
    asyncio.run(test_one_page_real())
