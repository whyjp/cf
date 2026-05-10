from camfit_crawl.parser import (
    detect_payload,
    parse_list_html,
    parse_list_json,
    _classify_facilities,
    _split_region,
)


SAMPLE_HTML = """
<html><body>
<ul>
  <li class="camp-card" data-camp-id="abc123">
    <a href="/camp/abc123">
      <img class="thumb" src="https://x/y.jpg"/>
      <h3 class="camp-name">계곡 캠프 X</h3>
      <div class="region">강원도 평창군</div>
      <span class="tag">계곡</span>
      <span class="tag">키즈캠핑</span>
      <span class="facility">트램펄린</span>
    </a>
  </li>
  <li class="camp-card" data-camp-id="def456">
    <a href="/camp/def456">
      <h3 class="camp-name">노을 캠프</h3>
      <div class="region">경기 가평군</div>
      <span class="facility">샤워실</span>
    </a>
  </li>
</ul>
</body></html>
"""


def test_parse_list_html_two_cards():
    rows = parse_list_html(SAMPLE_HTML)
    assert len(rows) == 2
    by_id = {r.id: r for r in rows}
    assert by_id["abc123"].name == "계곡 캠프 X"
    assert by_id["abc123"].has_valley is True
    assert by_id["abc123"].has_kids is True
    assert by_id["abc123"].has_trampoline is True
    assert by_id["abc123"].region_sido == "강원"
    assert by_id["abc123"].region_sigungu == "평창군"
    assert "계곡" in by_id["abc123"].categories
    assert by_id["def456"].has_trampoline is False


def test_parse_list_json_payload():
    payload = {
        "items": [
            {
                "id": "json-1",
                "name": "강가 캠프",
                "address": "충북 단양군",
                "lat": 36.98,
                "lng": 128.36,
                "categories": ["계곡", "키즈캠핑"],
                "facilities": ["전기", "샤워실"],
            }
        ]
    }
    rows = parse_list_json(payload)
    assert len(rows) == 1
    r = rows[0]
    assert r.id == "json-1"
    assert r.lat == 36.98
    assert r.has_valley is True
    assert r.has_kids is True
    assert r.has_trampoline is False
    assert r.region_sido == "충북"


def test_classify_facilities_keywords():
    flags = _classify_facilities("키즈캠핑 트램펄린 계곡")
    assert flags == {"has_valley": True, "has_kids": True, "has_trampoline": True}


def test_split_region_handles_short_address():
    assert _split_region("경기 양평군 일원") == ("경기", "양평군")
    assert _split_region(None) == (None, None)


def test_detect_payload_routes_correctly():
    assert detect_payload('{"items":[]}') == "json"
    assert detect_payload("<html></html>") == "html"
    assert detect_payload("") == "html"


def test_parse_list_html_anchor_cards_and_dedup():
    """SPA-style /camp/ links (no __NEXT_DATA__) + duplicate href ignored."""
    oid_a = "a" * 24
    oid_b = "b" * 24
    html = f"""
    <html><body>
      <a href="/camp/{oid_a}" class="card"><p class="typography-caption1 typography-bold">숲 캠프</p></a>
      <a href="/camp/{oid_b}"><img alt="강 캠프" src="/x.png"/></a>
      <a href="/camp/{oid_a}"><p class="typography-bold">숲 캠프 재노출</p></a>
    </body></html>
    """
    rows = parse_list_html(html)
    assert len(rows) == 2
    by_id = {r.id: r for r in rows}
    assert by_id[oid_a].name == "숲 캠프"
    assert by_id[oid_b].name == "강 캠프"


def test_parse_list_html_skips_non_oid_camp_href():
    rows = parse_list_html(
        '<html><body><a href="/camp/exhibition?type=main">배너</a>'
        '<a href="/camp/c0ffeec0ffeec0ffeecafe01"><p class="typography-bold">진짜</p></a></body></html>'
    )
    assert len(rows) == 1
    assert rows[0].id == "c0ffeec0ffeec0ffeecafe01"
