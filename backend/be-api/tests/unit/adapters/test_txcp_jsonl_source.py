"""TxcpJsonlSource — txcp camps.jsonl → DomainCamp adapter."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from cf_be_api.adapters.source.txcp_jsonl import TxcpJsonlSource


@pytest.fixture
def txcp_data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "txcp_data"
    d.mkdir()
    records = [
        {
            "id": "16706",
            "name": "노을진캠핑장",
            "region_sido": "인천",
            "region_sigungu": "서구",
            "address": "인천 서구 정서진로 500",
            "lat": None,
            "lon": None,
            "site_tp_codes": ["BB000", "BB001"],
            "thumbnail": "https://image.thankqcamping.com/file/x.jpg",
            "min_basic_price": 50000,
            "min_sale_price": 45000,
            "review_count": 12,
            "monthly_review_count": 3,
            "source": "thankqcamping",
            "pulled_at": "2026-05-10T00:00:00Z",
        },
        {
            "id": "17644",
            "name": "두번째캠핑장",
            "region_sido": "충북",
            "region_sigungu": "괴산군",
            "address": "충북 괴산군",
            "lat": 36.81,
            "lon": 127.79,
            "site_tp_codes": ["BB002"],
            "thumbnail": None,
            "min_basic_price": None,
            "min_sale_price": None,
            "review_count": 0,
            "monthly_review_count": 0,
            "source": "thankqcamping",
        },
    ]
    (d / "camps.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return d


def test_iter_summaries_yields_namespaced_ids(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    camps = list(src.iter_summaries())
    assert len(camps) == 2
    assert {c.id for c in camps} == {"txcp:16706", "txcp:17644"}


def test_camp_source_and_detail_url(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    by_id = {c.id: c for c in src.iter_summaries()}
    # campSeq == cseq (verified by detail-bridge probe 2026-05-10)
    assert by_id["txcp:16706"].source == "txcp"
    assert by_id["txcp:16706"].detail_url == (
        "https://m.thankqcamping.com/resv/view.hbb?cseq=16706"
    )
    assert by_id["txcp:17644"].detail_url == (
        "https://m.thankqcamping.com/resv/view.hbb?cseq=17644"
    )


def test_camp_korean_text_preserved(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    by_id = {c.id: c for c in src.iter_summaries()}
    c = by_id["txcp:16706"]
    assert c.name == "노을진캠핑장"
    assert c.region.sido == "인천"
    assert c.region.sigungu == "서구"


def test_camp_geo_when_present(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    by_id = {c.id: c for c in src.iter_summaries()}
    c1 = by_id["txcp:16706"]
    c2 = by_id["txcp:17644"]
    assert c1.geo is None  # lat/lon None
    assert c2.geo is not None
    assert abs(c2.geo.lat - 36.81) < 1e-6
    assert abs(c2.geo.lon - 127.79) < 1e-6


def test_site_tp_codes_to_korean_types(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    by_id = {c.id: c for c in src.iter_summaries()}
    assert "오토캠핑" in by_id["txcp:16706"].types
    assert "글램핑" in by_id["txcp:16706"].types
    assert "카라반" in by_id["txcp:17644"].types


def test_thumbnail_to_single_photo(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    by_id = {c.id: c for c in src.iter_summaries()}
    assert len(by_id["txcp:16706"].photos) == 1
    assert len(by_id["txcp:17644"].photos) == 0  # no thumbnail


def test_get_detail_falls_back_to_summary(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    c = src.get_detail("txcp:16706")
    assert c is not None
    assert c.id == "txcp:16706"
    # detail-bridge not implemented, still returns summary
    c2 = src.get_detail("16706")  # without prefix also resolves
    assert c2 is not None and c2.id == "txcp:16706"


def test_get_detail_returns_none_for_unknown(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    assert src.get_detail("txcp:99999") is None


def test_iter_reviews_empty_until_detail_bridge(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    assert list(src.iter_reviews("txcp:16706")) == []


def test_iter_filters_yields_5_site_tps(txcp_data_dir):
    src = TxcpJsonlSource(txcp_data_dir)
    filters = list(src.iter_filters())
    assert len(filters) == 5
    ids = [f[0] for f in filters]
    assert {"BB000", "BB001", "BB002", "BB003", "BB006"} == set(ids)
    for fid, name, kind, raw in filters:
        assert kind == "site_tp"
        assert raw == {"site_tp_code": fid}


def test_empty_jsonl_yields_zero_camps(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    (d / "camps.jsonl").write_text("", encoding="utf-8")
    src = TxcpJsonlSource(d)
    assert list(src.iter_summaries()) == []


def test_missing_jsonl_file(tmp_path):
    d = tmp_path / "nope"
    d.mkdir()
    src = TxcpJsonlSource(d)
    assert list(src.iter_summaries()) == []
