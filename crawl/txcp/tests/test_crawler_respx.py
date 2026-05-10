"""Crawler integration — respx 로 ax_list_search.hbb mocking.

S1 normal pull / S2 5xx retry / S5 empty stop / I-3 dedup / I-4 4xx budget.
"""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from tkcp_crawl import crawler as crawler_mod
from tkcp_crawl.settings import Settings


pytestmark = pytest.mark.asyncio


def _page_response(page_num: int, total: int, n_records: int = 20, base_seq: int = 0) -> dict:
    return {
        "code": 200,
        "data": {
            "totalCount": total,
            "campList": [
                {
                    "campSeq": base_seq + page_num * 100 + i,
                    "campName": f"camp-{base_seq + page_num * 100 + i}",
                    "addr": f"테스트시 {i}동",
                    "sido": "테스트",
                    "sigungu": "테스트시",
                    "campPicList": [],
                    "siteTps": "BB000",
                    "minBasicPrice": 10000 + i,
                }
                for i in range(n_records)
            ],
        },
    }


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path / "data", delay_min=0.001, delay_max=0.002, max_pages_default=10)


@respx.mock(assert_all_called=False)
async def test_full_pull_three_pages(settings: Settings, respx_mock):
    url = settings.base_url + "/resv/ax_list_search.hbb"
    respx_mock.post(url).mock(side_effect=[
        httpx.Response(200, json=_page_response(1, 60, n_records=20)),
        httpx.Response(200, json=_page_response(2, 60, n_records=20)),
        httpx.Response(200, json=_page_response(3, 60, n_records=20)),
        httpx.Response(200, json=_page_response(4, 60, n_records=0)),
    ])
    summary = await crawler_mod.pull(site_tp="BB000", max_pages=10, resume=False, settings=settings)
    assert summary.pages_fetched >= 3
    assert summary.new_records >= 40  # totalCount 60, margin 3 → stop early possible
    assert summary.skipped_duplicates == 0
    assert (settings.data_dir / "camps.jsonl").exists()
    assert (settings.data_dir / "camps.csv").exists()
    assert (settings.data_dir / "state.json").exists()


@respx.mock(assert_all_called=False)
async def test_repeat_pull_yields_zero_new(settings: Settings, respx_mock):
    """I-3 idempotent — 두번째 pull 은 신규 0."""
    url = settings.base_url + "/resv/ax_list_search.hbb"
    respx_mock.post(url).mock(side_effect=[
        httpx.Response(200, json=_page_response(1, 20, n_records=20)),
        httpx.Response(200, json=_page_response(2, 20, n_records=0)),
    ] * 4)
    s1 = await crawler_mod.pull(site_tp="BB000", max_pages=5, resume=False, settings=settings)
    assert s1.new_records == 20
    s2 = await crawler_mod.pull(site_tp="BB000", max_pages=5, resume=False, settings=settings)
    assert s2.new_records == 0
    assert s2.skipped_duplicates >= 0  # 빈 페이지 즉시 만나면 0


@respx.mock(assert_all_called=False)
async def test_5xx_retried_then_success(settings: Settings, respx_mock):
    """S2: 5xx 에 tenacity retry 후 success."""
    url = settings.base_url + "/resv/ax_list_search.hbb"
    respx_mock.post(url).mock(side_effect=[
        httpx.Response(503),
        httpx.Response(200, json=_page_response(1, 5, n_records=5)),
        httpx.Response(200, json=_page_response(2, 5, n_records=0)),
    ])
    summary = await crawler_mod.pull(site_tp="BB000", max_pages=5, resume=False, settings=settings)
    assert summary.new_records == 5


@respx.mock(assert_all_called=False)
async def test_empty_streak_terminates(settings: Settings, respx_mock):
    """S5: 3 빈 페이지 연속 → stop."""
    url = settings.base_url + "/resv/ax_list_search.hbb"
    respx_mock.post(url).mock(side_effect=[
        httpx.Response(200, json=_page_response(1, 100, n_records=0)),
        httpx.Response(200, json=_page_response(2, 100, n_records=0)),
        httpx.Response(200, json=_page_response(3, 100, n_records=0)),
        httpx.Response(200, json=_page_response(4, 100, n_records=20)),  # never reached
    ])
    summary = await crawler_mod.pull(site_tp="BB000", max_pages=10, resume=False, settings=settings)
    assert summary.stopped_reason == "empty_streak"
    assert summary.new_records == 0


@respx.mock(assert_all_called=False)
async def test_4xx_budget_breaks_pull(settings: Settings, respx_mock):
    """I-4: 4xx 가 페이지 10 윈도우에 ≥2 발견 시 break + state save (sprint-3 보강)."""
    url = settings.base_url + "/resv/ax_list_search.hbb"
    respx_mock.post(url).mock(side_effect=[
        httpx.Response(200, json=_page_response(1, 200, n_records=20)),
        httpx.Response(403),
        httpx.Response(403),  # 2번째 4xx → budget 초과 → break
        httpx.Response(200, json=_page_response(4, 200, n_records=20)),  # never reached
    ])
    summary = await crawler_mod.pull(site_tp="BB000", max_pages=10, resume=False, settings=settings)
    assert summary.stopped_reason == "4xx_budget"
    assert summary.new_records == 20  # only page 1 succeeded
    # state 가 page 1 에서 멈춰 저장되어야 — 이후 resume 가능성
    state_path = settings.data_dir / "state.json"
    assert state_path.exists()
