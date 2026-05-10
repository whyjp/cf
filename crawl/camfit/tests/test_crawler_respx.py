"""End-to-end crawler integration test with respx (HTTP mock) — covers stealth → endpoint discovery → JSON parse → pagination stop."""
from __future__ import annotations

import pytest
import respx
from httpx import Response

from camfit_crawl.crawler import CrawlConfig, crawl
from camfit_crawl.stealth import DelayConfig


# Realistic camfit-shaped JSON payload (based on common Korean SPA conventions).
PAGE1 = {
    "items": [
        {
            "id": "camp-001",
            "name": "평창 계곡 캠프",
            "address": "강원 평창군 진부면",
            "lat": 37.65,
            "lng": 128.55,
            "categories": ["계곡", "키즈캠핑"],
            "facilities": ["전기", "샤워실", "트램펄린"],
        },
        {
            "id": "camp-002",
            "name": "가평 노을 캠프",
            "address": "경기 가평군 청평면",
            "lat": 37.74,
            "lng": 127.42,
            "categories": ["가족"],
            "facilities": ["전기", "wifi"],
        },
    ]
}
PAGE2 = {
    "items": [
        {
            "id": "camp-003",
            "name": "단양 강가 캠프",
            "address": "충북 단양군 매포읍",
            "lat": 36.98,
            "lng": 128.36,
            "categories": ["계곡"],
            "facilities": ["전기"],
        }
    ]
}
PAGE3_EMPTY: dict = {"items": []}


@pytest.mark.asyncio
async def test_crawl_full_flow_via_respx(monkeypatch):
    # 빠른 테스트를 위해 polite delay 를 0 으로 단축. (실 환경은 stealth.DelayConfig 기본값 1.5~3.0s.)
    monkeypatch.setattr("camfit_crawl.stealth.DelayConfig", lambda: DelayConfig(min_s=0.0, max_s=0.0))

    cfg = CrawlConfig(page_size=10, max_pages=5)

    with respx.mock(assert_all_called=False) as router:
        router.get("https://camfit.co.kr/robots.txt").mock(
            return_value=Response(200, text="User-agent: *\nAllow: /\n")
        )
        # First-tried JSON candidate: /api/v1/camps
        router.get("https://camfit.co.kr/api/v1/camps").mock(
            side_effect=lambda req: _route(req)
        )

        rows = []
        async for r in crawl(cfg):
            rows.append(r)

    ids = [r.id for r in rows]
    assert ids == ["camp-001", "camp-002", "camp-003"]

    # Coordinate carry-through.
    by_id = {r.id: r for r in rows}
    assert by_id["camp-001"].lat == 37.65
    assert by_id["camp-001"].lon == 128.55

    # Category 4-axis flag derivation:
    assert by_id["camp-001"].has_valley is True
    assert by_id["camp-001"].has_kids is True
    assert by_id["camp-001"].has_trampoline is True
    assert by_id["camp-002"].has_valley is False
    assert by_id["camp-002"].has_kids is False
    assert by_id["camp-002"].has_trampoline is False
    assert by_id["camp-003"].has_valley is True


def _route(request) -> Response:
    page = request.url.params.get("page", "1")
    if page == "1":
        return Response(200, json=PAGE1)
    if page == "2":
        return Response(200, json=PAGE2)
    return Response(200, json=PAGE3_EMPTY)


@pytest.mark.asyncio
async def test_crawl_robots_disallow_blocks_endpoint(monkeypatch):
    monkeypatch.setattr("camfit_crawl.stealth.DelayConfig", lambda: DelayConfig(min_s=0.0, max_s=0.0))
    cfg = CrawlConfig(page_size=10, max_pages=5)

    with respx.mock(assert_all_called=False) as router:
        router.get("https://camfit.co.kr/robots.txt").mock(
            return_value=Response(200, text="User-agent: *\nDisallow: /api/\nDisallow: /camp\nDisallow: /camps\n")
        )
        # Endpoints exist but should never be hit due to robots.
        api_route = router.get("https://camfit.co.kr/api/v1/camps").mock(
            return_value=Response(200, json=PAGE1)
        )

        rows = []
        async for r in crawl(cfg):
            rows.append(r)

    assert rows == []
    assert not api_route.called, "robots.txt Disallow 무시됨 — stealth.allowed() 가 작동 안 함"
