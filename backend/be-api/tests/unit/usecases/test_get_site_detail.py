import pytest
from cf_be_api.domain.errors import CampNotFound
from cf_be_api.domain.models import Camp, CampConcept, Region, Review, Theme
from cf_be_api.usecases.get_site_detail import GetSiteDetail


class FakeCampReader:
    def __init__(self, camps): self._c = {c.id: c for c in camps}
    def get(self, i): return self._c.get(i)
    def iter_all(self): return iter(self._c.values())
    def list_filtered(self, **kw): return list(self._c.values())
    def count(self): return len(self._c)


class FakeReviewReader:
    def __init__(self, by_camp): self._d = by_camp
    def top_for(self, cid, n=3, sort="score"):
        return self._d.get(cid, [])[:n]
    def total_for(self, cid): return len(self._d.get(cid, []))
    def iter_for(self, cid): return iter(self._d.get(cid, []))


class FakeConceptRepo:
    def __init__(self, by_camp): self._d = by_camp
    def upsert_concept(self, *_): pass
    def assign(self, *_, **__): pass
    def for_camp(self, camp_id):
        return [CampConcept(camp_id=camp_id, concept_id=cid, score=score)
                for cid, score in self._d.get(camp_id, [])]
    def all(self): return []


class FakeThemeRepo:
    def __init__(self, by_camp): self._d = by_camp
    def replace_all(self, *_): pass
    def assign(self, *_): pass
    def for_camp(self, camp_id): return self._d.get(camp_id)
    def all(self): return list(set(self._d.values()))


def test_returns_full_detail_payload():
    camps = [Camp(id="c1", name="A", region=Region(sido="강원", sigungu="평창군"))]
    reviews = {"c1": [Review(id="r1", camp_id="c1", text="좋아요", score=88)]}
    concepts = {"c1": [("kids", 0.7), ("valley", 0.5)]}
    theme = Theme(id="t-001", label="가족여행", member_count=12)
    themes = {"c1": theme}
    out = GetSiteDetail(
        FakeCampReader(camps),
        FakeReviewReader(reviews),
        FakeConceptRepo(concepts),
        FakeThemeRepo(themes),
    ).execute("c1")
    assert out["camp"]["id"] == "c1"
    assert out["reviews_total"] == 1
    assert len(out["reviews_top"]) == 1
    assert out["reviews_top"][0]["score"] == 88
    assert {c["id"] for c in out["concepts"]} == {"kids", "valley"}
    assert out["theme"]["id"] == "t-001"


def test_camp_not_found_raises():
    with pytest.raises(CampNotFound):
        GetSiteDetail(
            FakeCampReader([]), FakeReviewReader({}), FakeConceptRepo({}), FakeThemeRepo({})
        ).execute("missing")


def test_no_theme_returns_null():
    camps = [Camp(id="c1", name="A", region=Region(sido="x", sigungu="y"))]
    out = GetSiteDetail(
        FakeCampReader(camps), FakeReviewReader({}), FakeConceptRepo({}), FakeThemeRepo({})
    ).execute("c1")
    assert out["theme"] is None
