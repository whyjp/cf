"""TkcpAdapter 파싱 — fixtures/page1_BB000_sample.json 기준."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from txcp_crawl.adapter import TkcpAdapter

FIX = Path(__file__).parent / "fixtures" / "page1_BB000_sample.json"


@pytest.fixture
def adapter() -> TkcpAdapter:
    return TkcpAdapter()


@pytest.fixture
def sample_response() -> dict:
    return json.loads(FIX.read_text(encoding="utf-8"))


def test_build_payload_minimum(adapter: TkcpAdapter):
    p = adapter.build_payload(1)
    assert p == {"page_num": "1", "view_type": "PIC", "ser_st": "N", "is_empty_button": "N"}


def test_build_payload_with_site_tp(adapter: TkcpAdapter):
    p = adapter.build_payload(3, site_tp="BB001")
    assert p["page_num"] == "3"
    assert p["ser_site_tp"] == "BB001"


def test_parse_returns_records_and_total(adapter: TkcpAdapter, sample_response: dict):
    result = adapter.parse_camp_list_response(sample_response)
    assert result.total_count == 9217
    assert len(result.records) == 3
    assert result.has_next is True


def test_parse_thumbnail_uses_sort_zero(adapter: TkcpAdapter, sample_response: dict):
    result = adapter.parse_camp_list_response(sample_response)
    first = result.records[0]
    # campPicList 의 sort=0 = b.jpg (in fixture)
    assert first.thumbnail == "https://example.com/b.jpg"


def test_parse_handles_empty_pic_list(adapter: TkcpAdapter, sample_response: dict):
    result = adapter.parse_camp_list_response(sample_response)
    third = result.records[2]
    assert third.thumbnail is None


def test_parse_korean_text_preserved(adapter: TkcpAdapter, sample_response: dict):
    result = adapter.parse_camp_list_response(sample_response)
    assert result.records[1].name == "두번째캠핑장"
    assert result.records[1].region_sido == "충북"


def test_parse_returns_at_most_20(adapter: TkcpAdapter):
    """I-1: page size invariant — 일반 응답에서 ≤20."""
    raw = {"code": 200, "data": {"totalCount": 9217, "campList": [{"campSeq": str(i), "campName": f"c{i}"} for i in range(20)]}}
    result = adapter.parse_camp_list_response(raw)
    assert len(result.records) == 20


def test_parse_raises_on_non_200(adapter: TkcpAdapter):
    with pytest.raises(ValueError):
        adapter.parse_camp_list_response({"code": 500, "data": {}})


def test_parse_empty_list_terminates(adapter: TkcpAdapter):
    """S5: 마지막 페이지 빈 list."""
    raw = {"code": 200, "data": {"totalCount": 9217, "campList": []}}
    result = adapter.parse_camp_list_response(raw)
    assert len(result.records) == 0
    assert result.has_next is False
