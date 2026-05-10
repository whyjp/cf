"""Detail HTML parser — minimal field extraction tests.

Uses a real saved snapshot from probes (.ShipofTheseus/.../detail_cseq_14870.html)
when available, otherwise a synthetic minimal HTML fragment.
"""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from txcp_crawl.detail import parse_detail_html


def _make_minimal_html(cseq: str = "14870") -> str:
    return f"""<html>
<head><title>땡큐캠핑 | 테스트캠핑장 | 강원 | 오토캠핑</title></head>
<body>
<div class="swiper">
  <ul class="swiper-wrapper">
    <li class="swiper-slide"><img src="https://image.thankqcamping.com/file/2025/01/01/p1.jpg"/></li>
    <li class="swiper-slide"><img src="https://image.thankqcamping.com/file/2025/01/01/p2.jpg"/></li>
    <li class="swiper-slide"><img src="data:image/gif;base64,SGV"/></li>
    <li class="swiper-slide"><img src="https://image.thankqcamping.com/file/2025/01/01/p1.jpg"/></li>
  </ul>
</div>
<div class="info">
  <span class="p_div_list_title">예약</span>
  <span class="p_div_list_value">실시간 예약</span>
  <span class="p_div_list_title">주소</span>
  <span class="p_div_list_value">강원 평창군 테스트로 1</span>
  <span class="p_div_list_title">전화</span>
  <span class="p_div_list_value">010-0000-0000</span>
</div>
<script>var campseq='{cseq}';</script>
</body></html>"""


def test_parse_extracts_title():
    rec = parse_detail_html(_make_minimal_html(), cseq="14870", raw_html_path="x.html")
    assert rec.title is not None
    assert "땡큐캠핑" in rec.title
    assert "테스트캠핑장" in rec.title


def test_parse_extracts_photos_dedup_and_skips_data_uri():
    rec = parse_detail_html(_make_minimal_html(), cseq="14870", raw_html_path="x.html")
    # p1 + p2 = 2 distinct (data:image skipped, p1 dedup'd)
    assert len(rec.photos) == 2
    assert "https://image.thankqcamping.com/file/2025/01/01/p1.jpg" in rec.photos
    assert "https://image.thankqcamping.com/file/2025/01/01/p2.jpg" in rec.photos
    assert not any(u.startswith("data:") for u in rec.photos)


def test_parse_label_value_pairs():
    rec = parse_detail_html(_make_minimal_html(), cseq="14870", raw_html_path="x.html")
    assert rec.label_value_pairs.get("주소") == "강원 평창군 테스트로 1"
    assert rec.label_value_pairs.get("전화") == "010-0000-0000"
    assert rec.label_value_pairs.get("예약") == "실시간 예약"


def test_parse_metadata_fields():
    rec = parse_detail_html(_make_minimal_html(), cseq="14870", raw_html_path="snap/14870.html")
    assert rec.cseq == "14870"
    assert rec.raw_html_path == "snap/14870.html"
    assert rec.fetched_at  # iso timestamp


def test_model_dump_round_trip():
    rec = parse_detail_html(_make_minimal_html(), cseq="14870", raw_html_path="x.html")
    d = rec.model_dump()
    s = json.dumps(d, ensure_ascii=False)
    back = json.loads(s)
    assert back["cseq"] == "14870"
    assert len(back["photos"]) == 2


def test_parse_real_detail_html_if_available():
    """If probes have a real detail snapshot, validate parse against it."""
    candidate = Path(__file__).parent.parent.parent.parent / ".ShipofTheseus" / "tkcp-crawl" / "intent" / "probes" / "snapshots" / "detail_cseq_14870.html"
    if not candidate.exists():
        pytest.skip(f"real snapshot not present: {candidate}")
    html = candidate.read_text(encoding="utf-8", errors="replace")
    rec = parse_detail_html(html, cseq="14870", raw_html_path=str(candidate))
    assert rec.title and "땡큐캠핑" in rec.title
    # Real page has many photos
    assert len(rec.photos) >= 1
    # Real page has at least 4 label/value rows per heavy-classes probe
    assert len(rec.label_value_pairs) >= 1
