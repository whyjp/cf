import pytest
from cf_be_api.domain.models import Camp, Region, GeoPoint, Review, Concept, Theme


def test_camp_basic_construction():
    c = Camp(id="abc", name="x", region=Region(sido="강원", sigungu="평창군"))
    assert c.id == "abc"
    assert c.region.sido == "강원"
    assert "has_valley" not in Camp.model_fields


def test_camp_no_legacy_boolean_columns():
    """Per spec §6: hardcoded has_valley/has_kids/has_trampoline are removed."""
    fields = Camp.model_fields
    assert "has_valley" not in fields
    assert "has_kids" not in fields
    assert "has_trampoline" not in fields


def test_geo_point_korean_bbox_validation():
    GeoPoint(lat=37.5, lon=127.0)  # Seoul, valid
    with pytest.raises(Exception):
        GeoPoint(lat=10.0, lon=120.0)  # outside Korea → must reject


def test_review_minimum_fields():
    r = Review(id="r1", camp_id="abc", text="좋아요")
    assert r.text == "좋아요"
    assert r.score is None


def test_concept_source_enum():
    Concept(id="kids", name="kids", source="hashtag")
    with pytest.raises(Exception):
        Concept(id="x", name="x", source="bogus_source")
