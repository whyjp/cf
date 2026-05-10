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


def test_get_detail_enriches_when_details_json_present(txcp_data_dir):
    """details/{cseq}.json present → photos extended + label_value_pairs surfaced."""
    details_dir = txcp_data_dir / "details"
    details_dir.mkdir()
    (details_dir / "16706.json").write_text(json.dumps({
        "cseq": "16706",
        "title": "땡큐캠핑 | 노을진캠핑장 | 인천",
        "photos": [
            "/file/2025/02/10/p1.jpg",
            "/file/2025/02/10/p2.jpg",
            "https://image.thankqcamping.com/file/x.jpg",  # already in summary
        ],
        "label_value_pairs": {
            "예약": "실시간 예약",
            "주소": "인천 서구 정서진로 500 (오류동) 상세",
            "전화": "032-000-0000",
        },
        "raw_html_path": "details_html/16706.html",
        "fetched_at": "2026-05-10T00:00:00Z",
    }, ensure_ascii=False), encoding="utf-8")

    src = TxcpJsonlSource(txcp_data_dir)
    enriched = src.get_detail("txcp:16706")
    assert enriched is not None
    # photos: summary had 1 (https://...x.jpg) + detail adds 2 host-relative absolutized
    photo_urls = {p.url for p in enriched.photos}
    assert "https://image.thankqcamping.com/file/2025/02/10/p1.jpg" in photo_urls
    assert "https://image.thankqcamping.com/file/2025/02/10/p2.jpg" in photo_urls
    assert "https://image.thankqcamping.com/file/x.jpg" in photo_urls
    assert len(enriched.photos) == 3
    # label_value_pairs surfaced
    assert enriched.contact == "032-000-0000"
    assert enriched.brief == "실시간 예약"
    assert enriched.address and "정서진로 500" in enriched.address


def test_get_detail_falls_back_when_no_details_json(txcp_data_dir):
    """details/{cseq}.json absent → summary returned untouched."""
    src = TxcpJsonlSource(txcp_data_dir)
    summary_only = src.get_detail("txcp:16706")
    assert summary_only is not None
    assert summary_only.contact is None
    assert summary_only.brief is None
    # photos = single thumbnail from summary
    assert len(summary_only.photos) == 1


def test_get_detail_robust_to_corrupt_details_json(txcp_data_dir):
    """Bad JSON in details/{cseq}.json → silent fallback to summary, no crash."""
    (txcp_data_dir / "details").mkdir()
    (txcp_data_dir / "details" / "16706.json").write_text("not json at all {", encoding="utf-8")
    src = TxcpJsonlSource(txcp_data_dir)
    camp = src.get_detail("txcp:16706")
    assert camp is not None
    assert camp.contact is None  # no enrichment happened


def test_pension_only_records_excluded_from_iter_summaries(tmp_path):
    """User directive 2026-05-10: 펜션 only 데이터는 파이프라인 처리 제외.

    Filter rule: BB003 in site_tp_codes AND no camping code (BB000/001/002/006).
    """
    d = tmp_path / "txcp_pension"
    d.mkdir()
    records = [
        {"id": "100", "name": "캠핑+펜션 겸업", "region_sido": "강원", "region_sigungu": "춘천",
         "site_tp_codes": ["BB000", "BB003"]},   # camping + pension → KEEP
        {"id": "200", "name": "글램핑만", "region_sido": "강원", "region_sigungu": "평창",
         "site_tp_codes": ["BB001"]},             # camping → KEEP
        {"id": "300", "name": "펜션 only", "region_sido": "제주", "region_sigungu": "서귀포",
         "site_tp_codes": ["BB003"]},             # pension only → DROP
        {"id": "400", "name": "펜션 + unknown", "region_sido": "제주", "region_sigungu": "제주시",
         "site_tp_codes": ["BB003", "BB008"]},    # pension + unknown, no camping → DROP
        {"id": "500", "name": "no site_tp", "region_sido": "경기", "region_sigungu": "가평",
         "site_tp_codes": []},                    # empty → KEEP (safe)
        {"id": "600", "name": "unknown only", "region_sido": "강원", "region_sigungu": "양양",
         "site_tp_codes": ["BB008"]},             # unknown only → KEEP (safe)
        {"id": "700", "name": "피크닉 only", "region_sido": "경기", "region_sigungu": "가평",
         "site_tp_codes": ["BB006"]},             # camping (피크닉) → KEEP
    ]
    (d / "camps.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    src = TxcpJsonlSource(d)
    yielded = {c.id for c in src.iter_summaries()}
    assert yielded == {"txcp:100", "txcp:200", "txcp:500", "txcp:600", "txcp:700"}
    assert "txcp:300" not in yielded
    assert "txcp:400" not in yielded
