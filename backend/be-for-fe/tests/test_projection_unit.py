"""projection.py 단위 테스트 — 통합 환경 없이도 PASS.

SP-A A3. 원본 cf_be_api/api.py 의 _filter_maritime_for_inland 등 동작을
BFF 로 옮긴 후의 동등성/회귀 방지.
"""
from __future__ import annotations

from cf_be_for_fe.projection import (
    camp_to_fe_row,
    filter_location_types_for_inland,
    filter_maritime_for_inland,
    project_camps,
    project_categories,
    project_site_detail,
)


def test_filter_maritime_for_inland_strips_ocean_token_in_landlocked():
    """충북 (내륙) 에서 '오션뷰' 같은 마커는 categories 에서 제거."""
    out = filter_maritime_for_inland(
        ["콜렉션:오션뷰 캠핑장", "키즈존", "바다 한 컷"], sido="충북",
    )
    assert out == ["키즈존"]


def test_filter_maritime_for_inland_passthrough_for_coastal_sido():
    """강원 (해안) 은 마커 보존."""
    out = filter_maritime_for_inland(
        ["콜렉션:오션뷰 캠핑장", "키즈존"], sido="강원",
    )
    assert out == ["콜렉션:오션뷰 캠핑장", "키즈존"]


def test_filter_location_types_for_inland_strips_ocean_island():
    """충북 의 location_types 에서 ocean / island 제거."""
    out = filter_location_types_for_inland(
        ["mountain", "ocean", "island", "lake"], sido="충북",
    )
    assert out == ["mountain", "lake"]


def test_project_categories_drops_crawler_prefixes_and_translates_types():
    """전시:/시군구:/검색: 접두 drop + types 한글 변환."""
    out = project_categories(
        ["전시:E1234", "시군구:서울/강남구", "검색:키즈", "콜렉션:한적한"],
        ["autoCamping", "glamping", "unknownType"],
    )
    assert out == ["콜렉션:한적한", "오토캠핑", "글램핑", "unknownType"]


def test_camp_to_fe_row_maps_nested_to_flat_with_axis_flags():
    """Camp.model_dump() 모양의 dict → fe-row 평탄화 + has_<axis> 플래그.

    valley 키워드(계곡) 가 hashtags 에 있으면 has_valley=True.
    """
    camp_dict = {
        "id": "c1",
        "name": "테스트 캠핑장",
        "region": {"sido": "강원", "sigungu": "춘천"},
        "address": "강원 춘천 어디",
        "geo": {"lat": 37.8, "lon": 127.7},
        "types": ["autoCamping"],
        "facilities": ["전기"],
        "additional_facilities": ["샤워실"],
        "location_types": ["mountain"],
        "hashtags": ["계곡 옆"],
        "collections": ["콜렉션:가족 친화"],
        "description": "단풍이 예쁜 곳",
        "brief": "",
        "num_of_reviews": 12,
        "bookmark_count": 3,
        "url": "https://example.com/c1",
    }
    row = camp_to_fe_row(camp_dict)
    assert row["id"] == "c1"
    assert row["sido"] == "강원"
    assert row["sigungu"] == "춘천"
    assert row["lat"] == 37.8
    assert row["lon"] == 127.7
    assert row["categories"] == ["콜렉션:가족 친화", "오토캠핑"]
    assert row["facilities"] == ["전기", "샤워실"]
    assert row["location_types"] == ["mountain"]
    assert row["hashtags"] == ["계곡 옆"]
    assert row["has_valley"] is True
    assert row["has_autumn"] is True   # description '단풍'
    assert row["has_kids"] is False


def test_project_camps_handles_empty_and_list():
    assert project_camps([]) == []
    rows = project_camps([
        {"id": "a", "name": "A", "region": {"sido": "강원", "sigungu": "x"}},
        {"id": "b", "name": "B", "region": {"sido": "충북", "sigungu": "y"}},
    ])
    assert [r["id"] for r in rows] == ["a", "b"]
    assert all("has_valley" in r for r in rows)


def test_project_site_detail_flat_camelcase_and_inland_filter():
    """/sites/{id} projection — flat camelCase + 내륙 maritime drop."""
    detail = {
        "camp": {
            "id": "c2",
            "name": "충북 호반",
            "region": {"sido": "충북", "sigungu": "단양"},
            "address": "충북 단양",
            "geo": {"lat": 36.9, "lon": 128.4},
            "types": ["autoCamping"],
            "collections": ["콜렉션:오션뷰", "콜렉션:한적한"],
            "hashtags": ["바다처럼"],
            "facilities": ["전기"],
            "additional_facilities": [],
            "description": "호수 옆",
            "brief": "조용",
            "location_brief": "단양읍",
            "contact": "010",
            "price_start_from": 30000,
            "price_end_to": 70000,
            "num_of_reviews": 5,
            "bookmark_count": 1,
            "url": "https://example.com/c2",
            "photos": [{"url": "u1", "thumb_url": "t1"}, {"url": "u2"}],
        },
        "reviews_total": 5,
        "reviews_top": [
            {"user_nick": "n", "season": "summer", "user_type": "solo",
             "num_of_days": 1, "score": 4.5, "text": "good"},
        ],
        "concepts": [{"id": "valley", "score": 0.9}],
        "theme": {"id": "t1", "label": "호반"},
    }
    flat = project_site_detail(detail)
    assert flat["id"] == "c2"
    assert flat["region_sido"] == "충북"
    assert flat["region_sigungu"] == "단양"
    # 내륙: 오션뷰/바다처럼 collections/hashtags 에서 drop
    assert flat["categories"] == ["콜렉션:한적한", "오토캠핑"]
    assert flat["hashtags"] == []
    # camelCase 매핑
    assert flat["locationBrief"] == "단양읍"
    assert flat["priceStartFrom"] == 30000
    assert flat["priceEndTo"] == 70000
    assert flat["numOfReviews"] == 5
    assert flat["bookmarkCount"] == 1
    # photos: thumb fallback 검증
    assert flat["photos"] == [
        {"url": "u1", "thumb": "t1"},
        {"url": "u2", "thumb": "u2"},
    ]
    # reviews_top 내부 키 매핑
    assert flat["reviews_top"][0] == {
        "user": "n", "season": "summer", "userType": "solo",
        "numOfDays": 1, "score": 4.5, "text": "good",
    }
    assert flat["concepts"] == [{"id": "valley", "score": 0.9}]
    assert flat["theme"] == {"id": "t1", "label": "호반"}
